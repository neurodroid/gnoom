/* 2010-10-28
   C. Schmidt-Hieber, University College London */

#include "dc1394.h"

#include <cstdio>
#include <stdbool.h>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <fstream>
#include <iomanip>
#include <ctime>
#include <sys/socket.h>
#ifndef INET
#include <sys/un.h>
#define SOCKTYPE AF_UNIX
#else
#include <netinet/in.h>
#include <netdb.h>
#define SOCKTYPE AF_INET
#endif
#include <sys/types.h>
#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <sstream>
#include <algorithm>
#include <cv.h>
#include <opencv2/imgproc.hpp>
#include <dc1394/dc1394.h>
#include <dc1394/vendor/avt.h>
#include <boost/filesystem.hpp>
#include <turbojpeg.h>
#include <jpeglib.h>
#include <png.h>
#include <queue>
#include <SDL.h>

#include "dc1394cam.h"
double tdiff(timespec time1, timespec time0) {
    return ( time1.tv_sec - time0.tv_sec )
         + ( time1.tv_nsec - time0.tv_nsec ) / BILLION;
}

double t2d(timespec time1) {
    return time1.tv_sec + time1.tv_nsec / BILLION;
}

dc1394cam gCamera;

void cleanup_and_exit(dc1394cam& camera);

struct saveframe {
    saveframe(const std::vector<unsigned char>& d, int w, int h, double ts, const std::string& fn="") :
        data(d), width(w), height(h), timestamp(ts), fname(fn) {}
    std::vector<unsigned char> data;
    int width;
    int height;
    double timestamp;
    std::string fname;
};

std::queue<saveframe> acq_frame_buffer;
pthread_mutex_t acq_buffer_mutex = PTHREAD_MUTEX_INITIALIZER;
pthread_mutex_t camera_mutex = PTHREAD_MUTEX_INITIALIZER;

void* thread_acq_image(void*) {
    timespec time_save0, time_save1, t_sleep, t_rem;
    t_sleep.tv_sec = 0;
    t_sleep.tv_nsec = 10;

    dc1394video_frame_t *frame;

    for (;;) {
        /* wait for image */
        pthread_mutex_lock( &camera_mutex );
        int ret = gCamera.wait_for_image(1);
        pthread_mutex_unlock( &camera_mutex );
        if (ret) {
            pthread_mutex_lock( &camera_mutex );
            dc1394error_t err = dc1394_capture_dequeue(gCamera.cam(), DC1394_CAPTURE_POLICY_POLL, &frame);
            /* frame->timestamp appears to be broken, so we have to resort to clock_gettime */
            timespec fts;
            clock_gettime( CLOCK_REALTIME, &fts );
            double ft = t2d(fts);
            pthread_mutex_unlock( &camera_mutex );
            if (err) {
                cleanup_and_exit(gCamera);
                std::cerr << dc1394_error_get_string(err) << "\nCould not capture frame" << std::endl;
            }

            // return frame to ring buffer:
            // if (frame->image) {
                pthread_mutex_lock( &camera_mutex );
                err = dc1394_capture_enqueue(gCamera.cam(), frame);
                pthread_mutex_unlock( &camera_mutex );
                if (err) {
                    std::cerr << dc1394_error_get_string(err) << "\nCould not return frame to ring buffer" << std::endl;
                    cleanup_and_exit(gCamera);
                }
                // }
            int width = frame->size[0];
            int height = frame->size[1];
            pthread_mutex_lock( &acq_buffer_mutex );
            acq_frame_buffer.push(saveframe(std::vector<unsigned char>(&(frame->image)[0],
                                                                       &(frame->image)[width*height]),
                                            width, height, ft)); // (double)frame->timestamp));
            pthread_mutex_unlock( &acq_buffer_mutex );
        } else {
            nanosleep(&t_sleep, &t_rem);
        }
    }
}

#define LICKOMETER

#ifdef LICKOMETER
const static int LICK_FRAME_THRESHOLD = 35;
const static int LICK_SUM_THRESHOLD = 700000000;
#else

#include <pthread.h>

pthread_mutex_t save_buffer_mutex = PTHREAD_MUTEX_INITIALIZER;

std::queue<saveframe> save_frame_buffer;
std::vector<png_bytep> pngdata(480);

void* thread_save_image(void*);

void write_jpeg(const saveframe& sframe) {
    /* This struct contains the JPEG compression parameters and pointers to
     * working space (which is allocated as needed by the JPEG library).
     * It is possible to have several such structures, representing multiple
     * compression/decompression processes, in existence at once.  We refer
     * to any one struct (and its associated working data) as a "JPEG object".
     */
    struct jpeg_compress_struct cinfo;
    /* This struct represents a JPEG error handler.  It is declared separately
     * because applications often want to supply a specialized error handler
     * (see the second half of this file for an example).  But here we just
     * take the easy way out and use the standard error handler, which will
     * print a message on stderr and call exit() if compression fails.
     * Note that this struct must live as long as the main JPEG parameter
     * struct, to avoid dangling-pointer problems.
     */
    struct jpeg_error_mgr jerr;
    /* More stuff */
    FILE * outfile;		/* target file */
    JSAMPROW row_pointer[1];	/* pointer to JSAMPLE row[s] */
    int row_stride;		/* physical row width in image buffer */
    int quality = 95;

    /* Step 1: allocate and initialize JPEG compression object */

    /* We have to set up the error handler first, in case the initialization
     * step fails.  (Unlikely, but it could happen if you are out of memory.)
     * This routine fills in the contents of struct jerr, and returns jerr's
     * address which we place into the link field in cinfo.
     */
    cinfo.err = jpeg_std_error(&jerr);
    /* Now we can initialize the JPEG compression object. */
    jpeg_create_compress(&cinfo);

    /* Step 2: specify data destination (eg, a file) */
    /* Note: steps 2 and 3 can be done in either order. */

    /* Here we use the library-supplied code to send compressed data to a
     * stdio stream.  You can also write your own code to do something else.
     * VERY IMPORTANT: use "b" option to fopen() if you are on a machine that
     * requires it in order to write binary files.
     */
    if ((outfile = fopen(sframe.fname.c_str(), "wb")) == NULL) {
        fprintf(stderr, "can't open %s\n", sframe.fname.c_str());
        return;
    }
    jpeg_stdio_dest(&cinfo, outfile);

    /* Step 3: set parameters for compression */

    /* First we supply a description of the input image.
     * Four fields of the cinfo struct must be filled in:
     */
    cinfo.image_width = sframe.width; 	/* image width and height, in pixels */
    cinfo.image_height = sframe.height;
    cinfo.input_components = 1;// 3;		/* # of color components per pixel */
    cinfo.in_color_space = JCS_GRAYSCALE; // RGB; 	/* colorspace of input image */
    /* Now use the library's routine to set default compression parameters.
     * (You must set at least cinfo.in_color_space before calling this,
     * since the defaults depend on the source color space.)
     */
    jpeg_set_defaults(&cinfo);
    /* Now you can set any non-default parameters you wish to.
     * Here we just illustrate the use of quality (quantization table) scaling:
     */
    jpeg_set_quality(&cinfo, quality, TRUE /* limit to baseline-JPEG values */);

    /* Step 4: Start compressor */

    /* TRUE ensures that we will write a complete interchange-JPEG file.
     * Pass TRUE unless you are very sure of what you're doing.
     */
    jpeg_start_compress(&cinfo, TRUE);

    /* Step 5: while (scan lines remain to be written) */
    /*           jpeg_write_scanlines(...); */

    /* Here we use the library's state variable cinfo.next_scanline as the
     * loop counter, so that we don't have to keep track ourselves.
     * To keep things simple, we pass one scanline per call; you can pass
     * more if you wish, though.
     */
    row_stride = sframe.width * 1;//3;	/* JSAMPLEs per row in image_buffer */

    while (cinfo.next_scanline < cinfo.image_height) {
      /* jpeg_write_scanlines expects an array of pointers to scanlines.
       * Here the array is only one element long, but you could pass
       * more than one scanline at a time if that's more convenient.
       */
        row_pointer[0] = (JSAMPLE*)& sframe.data[cinfo.next_scanline * row_stride];
      (void) jpeg_write_scanlines(&cinfo, row_pointer, 1);
    }

    /* Step 6: Finish compression */

    jpeg_finish_compress(&cinfo);
    /* After finish_compress, we can close the output file. */
    fclose(outfile);

    /* Step 7: release JPEG compression object */

    /* This is an important step since it will release a good deal of memory. */
    jpeg_destroy_compress(&cinfo);

    /* And we're done! */

}

int write_png(const saveframe& sframe) {
    FILE *fp;
    png_structp png_ptr;
    png_infop info_ptr;
    png_colorp palette;
    png_color_8 sig_bit;
    int pass, number_passes;

    /* open the file */
    fp = fopen(sframe.fname.c_str(), "wb");
    if (fp == NULL) {
        std::cerr << "Couldn't create file" << std::endl;
        return 0;
    }
    /* Create and initialize the png_struct with the desired error
     * handler functions.
     * If you want to use the default stderr and longjump method,
     * you can supply NULL for the last three parameters (which we do).
     * We also check that the library version is compatible with
     * the one used at compile time, in case we are using dynamically
     * linked libraries.  REQUIRED.
     */
    png_ptr = png_create_write_struct(PNG_LIBPNG_VER_STRING,
                                      NULL, NULL, NULL);

    if (png_ptr == NULL) {
        fclose(fp);
        std::cerr << "Couldn't create write struct" << std::endl;
        return 0;
    }

    /* Allocate/initialize the image information data.  REQUIRED */
    info_ptr = png_create_info_struct(png_ptr);
    if (info_ptr == NULL)
    {
        fclose(fp);
        png_destroy_write_struct(&png_ptr,  (png_infopp)NULL);
        std::cerr << "Couldn't create info struct" << std::endl;
        return 0;
    }

    /* Set error handling.  REQUIRED if you aren't supplying your own
     * error handling functions in the png_create_write_struct() call.
     */
    if (setjmp(png_ptr->jmpbuf))
    {
        /* If we get here, we had a problem reading the file */
        fclose(fp);
        png_destroy_write_struct(&png_ptr,  (png_infopp)NULL);
        std::cerr << "Couldn't create info struct" << std::endl;
        return 0;
    }

    png_set_compression_level(png_ptr, Z_BEST_SPEED);
    png_set_filter(png_ptr, PNG_FILTER_TYPE_BASE, PNG_FILTER_UP);

    /* One of the following I/O initialization functions is REQUIRED */
    /* set up the output control if you are using standard C streams */
    png_init_io(png_ptr, fp);
    if (setjmp(png_ptr->jmpbuf))
    {
        /* If we get here, we had a problem reading the file */
        fclose(fp);
        png_destroy_write_struct(&png_ptr,  (png_infopp)NULL);
        std::cerr << "Couldn't init io" << std::endl;
        return 0;
    }

    /* Set the image information here.  Width and height are up to 2^31,
     * bit_depth is one of 1, 2, 4, 8, or 16, but valid values also
     * depend on the color_type selected.
     * color_type is one of PNG_COLOR_TYPE_GRAY,
     * PNG_COLOR_TYPE_GRAY_ALPHA, PNG_COLOR_TYPE_PALETTE,
     * PNG_COLOR_TYPE_RGB, or PNG_COLOR_TYPE_RGB_ALPHA.
     * Interlacing is either PNG_INTERLACE_NONE or PNG_INTERLACE_ADAM7,
     * and the compression_type and filter_type MUST currently be
     * PNG_COMPRESSION_TYPE_BASE and PNG_FILTER_TYPE_BASE. REQUIRED
     */
    png_set_IHDR(png_ptr, info_ptr, sframe.width, sframe.height,
                 8,
                 PNG_COLOR_TYPE_GRAY,
                 PNG_INTERLACE_NONE,
                 PNG_COMPRESSION_TYPE_BASE,
                 PNG_FILTER_TYPE_BASE);
    if (setjmp(png_ptr->jmpbuf))
    {
        /* If we get here, we had a problem reading the file */
        fclose(fp);
        png_destroy_write_struct(&png_ptr,  (png_infopp)NULL);
        std::cerr << "Couldn't set header" << std::endl;
        return 0;
    }

    /* Write the file header information.  REQUIRED */
    png_write_info(png_ptr, info_ptr);
    if (setjmp(png_ptr->jmpbuf))
    {
        /* If we get here, we had a problem reading the file */
        fclose(fp);
        png_destroy_write_struct(&png_ptr,  (png_infopp)NULL);
        std::cerr << "Couldn't write info" << std::endl;
        return 0;
    }

    /* The easiest way to write the image is to write it in one go. */
    if (pngdata.size()!=sframe.height)
        pngdata.resize(sframe.height);
    for (int nr=0; nr<sframe.height; ++nr) {
        pngdata[nr] = (png_bytep) &(sframe.data[nr*sframe.width]);
    }
    std::cout << "Writing image... " << std::flush;

    timespec time0, time1;
    clock_gettime( CLOCK_REALTIME, &time0);
    png_write_image(png_ptr, &(pngdata[0]));
    if (setjmp(png_ptr->jmpbuf))
    {
        /* If we get here, we had a problem reading the file */
        fclose(fp);
        png_destroy_write_struct(&png_ptr,  (png_infopp)NULL);
        std::cerr << "Couldn't write image" << std::endl;
        return 0;
    }

    clock_gettime( CLOCK_REALTIME, &time1);
    double frame_dur = tdiff(time1, time0);
    std::cout << frame_dur*1e3 << std::endl;
    
    /* It is REQUIRED to call this to finish writing the rest of the file */
    png_write_end(png_ptr, info_ptr);

    /* clean up after the write, and free any memory allocated */
    png_destroy_write_struct(&png_ptr, (png_infopp)NULL);

    /* close the file */
    fclose(fp);

    /* that's it */
    return 1;
}

void* thread_save_image(void*) {
    timespec time_save0, time_save1, t_sleep, t_rem;
    t_sleep.tv_sec = 0;
    t_sleep.tv_nsec = 10;

    for (;;) {
        // Wait for image capture
        if (save_frame_buffer.size() > 0) {
            clock_gettime( CLOCK_REALTIME, &time_save0);
            write_jpeg(save_frame_buffer.front());
            // write_png(save_frame_buffer.front());
            if (save_frame_buffer.size() > 4) {
                int bufsize = save_frame_buffer.front().width *
                    save_frame_buffer.front().height *
                    save_frame_buffer.size() / 1024.0; 
                std::cout << "\rBuffer queue: "
                          <<  bufsize << " kB                     " << std::flush;
            }
            std::cout << "d" << std::flush;
            pthread_mutex_lock( &save_buffer_mutex );
            save_frame_buffer.pop();
            pthread_mutex_unlock( &save_buffer_mutex );
            
            clock_gettime(CLOCK_REALTIME, &time_save1);
            double twrite = tdiff(time_save1, time_save0);
        } else {
            nanosleep(&t_sleep, &t_rem);
        }
    }
}
#endif

void write_send(int socket, double timestamp, const std::string& fname, int& ncount) {
    timespec time1;
    clock_gettime( CLOCK_REALTIME, &time1);
    double dtime1 = timestamp; // t2d(time1);
    
#ifndef STANDALONE
    while (send(socket, &dtime1, sizeof(double), 0) < 0) {
        perror("DC1394: client: send");
    }
#endif

    // Actual Writing happens in get_image

    ncount++;
    
}

int get_image(cv::Mat& im, const cv::Mat& mapping, bool rotate, int socket,
              const std::string& fname, int& ncount)
{
    int nframes = 0;
    /* empty the acquired frame buffer */
    while (acq_frame_buffer.size() > 0) {

        int width = acq_frame_buffer.front().width;
        int height = acq_frame_buffer.front().height;
        double timestamp = acq_frame_buffer.front().timestamp;

#ifndef LICKOMETER
        if (fname != "") {
            std::ostringstream jpgname;
            jpgname << fname << std::setfill('0') << std::setw(7) << ncount << ".jpg";
            pthread_mutex_lock( &save_buffer_mutex );
            save_frame_buffer.push(saveframe(acq_frame_buffer.front().data,
                                             width, height, timestamp, jpgname.str()));
            pthread_mutex_unlock( &save_buffer_mutex );
        }
#endif

        pthread_mutex_lock( &acq_buffer_mutex );
        im = cv::Mat(cv::Size(width, height), CV_8UC1, &acq_frame_buffer.front().data[0]).clone();
        if (rotate) {
            cv::Mat cpim = im.clone();
            cv::warpAffine(cpim, im, mapping, im.size());
        }
        acq_frame_buffer.pop();
        pthread_mutex_unlock( &acq_buffer_mutex );
        if (fname != "") {
            write_send(socket, timestamp, fname, ncount);
        }

        nframes++;
    }
    return nframes;
}

/* turn color to gray */
cv::Mat bgr2gray(const cv::Mat& im) {
    cv::Mat gray;
    cv::cvtColor(im, gray, CV_BGR2GRAY);
    return gray;
}

/* apply gaussian blur */
cv::Mat gaussian_blur(const cv::Mat& im, const cv::Size ksize=cvSize(21,21), const double sigmaX=0) {
    cv::Mat blur; 
    cv::GaussianBlur(im, blur, ksize, sigmaX);
    return blur;
}


/* threshold frame */
cv::Mat thresholding(const cv::Mat& im, const int threshold_value=177, 
                     const int maxval=255, const int type=CV_THRESH_BINARY) {
    cv::Mat thresh;
    cv::threshold(im, thresh, threshold_value, maxval, type);
    return thresh;
}


int main (int argc, char **argv)
{

    
    char* ntry = (char*)"";
    if (argc > 1) {
        ntry = argv[1];
    }

    double fps = FPS;
    double target_dur = 1.0/fps;
    double tol = 1.0e-3;
    double total_dur = 0.0;

    dc1394_t * d = dc1394_new(); 
    if (!d) {
        return 1;
    }
    dc1394camera_list_t * list;
    dc1394error_t err = dc1394_camera_enumerate (d, &list);
    DC1394_ERR_RTN(err,"Failed to enumerate cameras");
    if (list->num == 0) {                                                  /* Verify that we have at least one camera */
        dc1394_log_error("No cameras found");
        return 1;
    }

    gCamera.init(d, list->ids[0].guid);
    if (!gCamera.cam()) {
        dc1394_log_error("Failed to initialize camera with guid %ld", list->ids[0].guid);
        dc1394_camera_free_list (list);

        return 1;
    }
    dc1394_camera_free_list (list);

    /*-----------------------------------------------------------------------
     *  have the camera start sending us data
     *-----------------------------------------------------------------------*/
    err = gCamera.start_transmission();
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(gCamera),"Could not start camera iso transmission");

    
    /*-----------------------------------------------------------------------
     *  capture one frame
     *-----------------------------------------------------------------------*/
    uint32_t width = 0;
    uint32_t height = 0;
    gCamera.get_image_size(&width, &height);
    cv::Mat mapping = cv::getRotationMatrix2D(cv::Point2f(width/2.0, height/2.0), 180.0, 1.0);

#ifdef USE_SDL
    static char *var = (char*)"SDL_VIDEO_WINDOW_POS=\"1280,480\"";
    int ret = putenv(var);
    
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        std::cerr << "DC1394: Unable to initialize SDL: " <<  SDL_GetError() << std::endl;
        return 1;
    }
    atexit(SDL_Quit);
    SDL_Surface *screen;
    screen = SDL_SetVideoMode(width, height, 24, SDL_HWSURFACE);
    if (screen == NULL) {
        std::cerr << "DC1394: Unable to set SDL video mode:" << SDL_GetError() << std::endl;
    }
    SDL_Event event;
#endif

#ifndef LICKOMETER    
    pthread_t save_thread, acq_thread;
    pthread_create( &save_thread, NULL, &thread_save_image, NULL);
#endif

    pthread_t save_thread, acq_thread;
    pthread_create( &acq_thread, NULL, &thread_acq_image, NULL);

    timespec t_sleep, t_rem;
    t_sleep.tv_sec = 0;
    t_sleep.tv_nsec = 1000;
    
#ifndef STANDALONE
    int s;
    if ((s = socket(SOCKTYPE, SOCK_STREAM, 0)) < 0) {
        perror("DC1394: client: socket");
        cleanup_and_exit(gCamera);
        return 1;
    }

    /*
     * Create the address we will be connecting to.
     */
#ifndef INET
    sockaddr_un sa;
    sa.sun_family = AF_UNIX;

    std::ostringstream tmpfn;
    tmpfn << "fwsocket" << ntry;
    std::cout << "DC1394: socket name " << tmpfn.str() << std::endl;
    
    int nameLen = strlen(tmpfn.str().c_str());
    if (nameLen >= (int) sizeof(sa.sun_path) -1) { /* too long? */
        cleanup_and_exit(gCamera);
        return 1;
    }
    
    sa.sun_path[0] = '\0';  /* abstract namespace */
    strcpy(sa.sun_path+1, tmpfn.str().c_str());
    int len = 1 + nameLen + offsetof(struct sockaddr_un, sun_path);
#else
    sockaddr_in sa;
    bzero((char *) &sa, sizeof(sa));
    sa.sin_family = AF_INET;
    hostent *server = gethostbyname("128.40.156.129");
    bcopy((char *)server->h_addr, 
          (char *)&sa.sin_addr.s_addr,
          server->h_length);
    sa.sin_port = htons(35000);
    int len = sizeof(sa);
#endif    
    /*
     * Try to connect to the address.  For this to
     * succeed, the server must already have bound
     * this address, and must have issued a listen()
     * request.
     *
     * The third argument indicates the "length" of
     * the structure, not just the length of the
     * socket name.
     */
    std::cout << "DC1394: Waiting for connection... " << std::flush;
    while (true) {
        // wait for connection:
        if (connect(s, (sockaddr*)&sa, len) < 0) {
            nanosleep(&t_sleep, &t_rem);
        } else {
            break;
        }
    }
    std::cout << "done" << std::endl;
    bool connected = false;
    std::vector<char> data(BUFSIZE);
    int nrec = recv(s, &data[0], data.size(), 0);
    std::string datastr(data.begin(), data.end());
    if (nrec<=0) {
        std::cerr << "DC1394: Didn't receive start message; exiting now" << std::endl;
        cleanup_and_exit(gCamera);
	close(s);
        return 1;
    }
    connected = true;
    
    std::string ready = "ready";
    while (send(s, ready.c_str(), ready.size(), 0) < 0) {
        perror("DC1394: client: send");
    }

    int flags = 0;
    if (-1 == (flags = fcntl(s, F_GETFL, 0)))
        flags = 0;

    if (fcntl(s, F_SETFL, flags | O_NONBLOCK)==-1) {
        perror("DC1394: client: unblock");
    }
#endif
    
    /* pthread_mutex_lock( &camera_mutex );
       gCamera.wait_for_trigger();
       pthread_mutex_unlock( &camera_mutex );

       Wait for acq_frame_buffer to fill instead
    */
    

    int ncount = 0;
    cv::Mat im(cv::Size(width, height), CV_8UC1);
    cv::Mat thresh = cv::Mat::ones(cv::Size(width, height), CV_8UC1);
    cv::Mat prevs(cv::Size(width, height), CV_8UC1);
    cv::Mat gray(cv::Size(width, height), CV_8UC1);
    
    // wait for image:
    int nframes = get_image(im, mapping, false, -1, "", ncount);
    std::cout << "DC1394: Waiting for first image to arrive... " << std::flush;
    int nwait = 0;
    while (!nframes) {
        nanosleep(&t_sleep, &t_rem);
        std::cout << "." << std::flush;
        nframes = get_image(im, mapping, false, -1, "", ncount);
        nwait++;
#ifdef STANDALONE
	if (nwait > 1000) {
#else
	if (nwait > 100000) {
#endif
            std::cout << "Time out, stopping now\n";
            cleanup_and_exit(gCamera);
	}
    }
    timespec time0;
    clock_gettime(CLOCK_REALTIME, &time0);
    std::cout << "DC1394: image arrived: "
              << IplImage(im).depth << " bits, "
              << IplImage(im).nChannels << " channels, "
              << IplImage(im).widthStep << " step width"  << std::endl;

#ifdef USE_SDL
    SDL_Surface *surface =
        SDL_CreateRGBSurfaceFrom((void*)im.data,
                                 im.cols,
                                 im.rows,
                                 IplImage(im).depth*IplImage(im).nChannels,
                                 IplImage(im).widthStep,
                                 0xffffff, 0xffffff, 0xffffff, 0);
    screen = SDL_GetVideoSurface();
    if(SDL_BlitSurface(surface, NULL, screen, NULL) == 0)
        SDL_UpdateRect(screen, 0, 0, 0, 0);
#else
    cv::namedWindow("DC1394", CV_WINDOW_AUTOSIZE);
    cvMoveWindow("DC1394", 1280, 480);

    cv::imshow("DC1394", im);
#endif

    timespec time1 = time0;
    timespec time2 = time0;
    timespec time3 = time0;
    timespec time4 = time0;
    timespec t_disconnect = time0;
    timespec t_notrigger = time0;

#ifdef STANDALONE
    int s = -1;
#endif

    std::string fn = "";
#ifdef LICKOMETER
    std::string fn_lick = "";
    FILE* fp_lick = NULL;
#endif
    int key = 0;
    int nloop = 0;
    while (true) {
        clock_gettime( CLOCK_REALTIME, &time1);
#ifndef STANDALONE
        std::vector<char> data(BUFSIZE);
        int nrec = recv(s, &data[0], data.size(), 0);
        std::string datastr(data.begin(), data.end());
#endif

        nframes += get_image(im, mapping, false, s, fn, ncount);

#ifndef STANDALONE

        // no update from blender in a long time, terminate process
        if (datastr.find("1")==std::string::npos) {
            if (connected) {
                t_disconnect = time1;
                connected = false;
            } else {
                if (tdiff(time1, t_disconnect) > TIMEOUT) {
                    std::cout << "DC1394: Received termination signal" << std::endl;
                    close(s);
                    pthread_cancel(acq_thread);
                    pthread_cancel(save_thread);
                    return 0;
                }
            }
        } else {
            connected = true;
        }

	/* Explicit termination */
        if (datastr.find("quit")!=std::string::npos) {
            std::cout << "DC1394: Game over signal." << std::endl;
            std::string sclose = "close";
            while (send(s, sclose.c_str(), sclose.size(), 0) < 0) {
                perror("DC1394: client: send");
            }
            close(s);
            pthread_cancel(acq_thread);
            pthread_cancel(save_thread);
            return 0;
        }

        // Stop recording
        if (datastr.find("stop") != std::string::npos && fn != "") {
            fn = "";
#ifdef LICKOMETER
	    fn_lick = "";
	    if (fp_lick) {
                fclose(fp_lick);
		fp_lick = NULL;
            }
#endif
            std::cout << "DC1394: Stopping video" << std::endl;
            connected = true;
            ncount = 0;
        }

        // Start recording
        if (datastr.find("avi") != std::string::npos && datastr.find("stop") == std::string::npos && fn == "") {
            std::size_t startpos = datastr.find("begin")+5; 
            std::size_t endpos = datastr.find("end") - datastr.find("begin") - 5; 
            fn = datastr.substr(startpos, endpos);
            fn = std::string(trunk) + "data/" + fn;
#ifdef LICKOMETER
	    fn_lick = fn + "_lick";
	    fp_lick = fopen(fn_lick.c_str(), "wb");
            std::cout << "DC1394: Recording lick detection, writing to " << fn_lick << std::endl;
#else
            boost::filesystem::path path(fn);
            boost::filesystem::path writepath(path);

            // Test whether dir exists:
            if (!boost::filesystem::exists(writepath)) {
                std::cout << "DC1394: Creating directory " << writepath << std::endl;
                boost::filesystem::create_directories(writepath);
            }
            fn += "/";

            /* check save frame buffer */
            std::size_t nfb = save_frame_buffer.size();
            if (nfb)
                std::cerr << "DC1394: Frame buffer isn't empty!" << std::endl;

            std::cout << "DC1394: Starting video, writing to " << fn << std::endl;
            connected = true;
            ncount = 0;
#endif
        }
#endif // #nstandalone

#ifdef USE_SDL
        if (SDL_PollEvent(&event)) {
#ifdef STANDALONE
            /* Any of these event types will end the program */
            if (event.type == SDL_QUIT
                || event.type == SDL_KEYDOWN
                || event.type == SDL_KEYUP) {
                std::cout << std::endl;
                std::cout << std::endl << "DC1394: Total number of frames was " << nframes << std::endl;
                std::cout << std::endl << "DC1394: Frame buffer: " << acq_frame_buffer.size() << " frames left" << std::endl;
                close(s);
                pthread_cancel(acq_thread);
                pthread_cancel(save_thread);
                return 0;
            }
#endif // STANDALONE
        }
        surface->pixels = (void*)im.data;
        // SDL_CreateRGBSurfaceFrom((void*)IplImage(im).imageData,
        //                          IplImage(im).width,
        //                          IplImage(im).height,
        //                          IplImage(im).depth*IplImage(im).nChannels,
        //                          IplImage(im).widthStep,
        //                          1, 1, 1, 0);
        screen = SDL_GetVideoSurface();
        if(SDL_BlitSurface(surface, NULL, screen, NULL) == 0)
            SDL_UpdateRect(screen, 0, 0, 0, 0);
#else // not SDL
        key = cv::waitKey(2);
        cv::imshow("DC1394", im);
        if (key == 1114155 || key == 65579 || key==43 /*+*/) {
            uint32_t gain = 0;
            err = dc1394_feature_get_value(gCamera.cam(), DC1394_FEATURE_GAIN, &gain);
            DC1394_ERR_CLN_RTN(err,cleanup_and_exit(gCamera),"Can't get gain");
            if (gain < gCamera.get_maxgain()-10) {
                gain += 10;
                pthread_mutex_lock( &camera_mutex );
                err = dc1394_feature_set_value(gCamera.cam(), DC1394_FEATURE_GAIN, gain);
                pthread_mutex_unlock( &camera_mutex );
                std::cout << "DC1394: New gain value: " << gain << std::endl;
                DC1394_ERR_CLN_RTN(err,cleanup_and_exit(gCamera),"Can't set gain");
            }
        }
        if (key == 1114207 || key == 45 /*-*/) {
            uint32_t gain = 0;
            err = dc1394_feature_get_value(gCamera.cam(), DC1394_FEATURE_GAIN, &gain);
            DC1394_ERR_CLN_RTN(err,cleanup_and_exit(gCamera),"Can't get gain");
            if (gain > gCamera.get_mingain()+10) {
                gain -= 10;
                pthread_mutex_lock( &camera_mutex );
                err = dc1394_feature_set_value(gCamera.cam(), DC1394_FEATURE_GAIN, gain);
                pthread_mutex_unlock( &camera_mutex );
                DC1394_ERR_CLN_RTN(err,cleanup_and_exit(gCamera),"Can't set gain");
            }
        }
#endif // not SDL

#ifdef LICKOMETER        
	/* IS THIS ALL YOU NEED THEN?
	   Lick detection */
	/* Not required because the captured image is already gray
	   cv::Mat gray = bgr2gray(im); */
	gray = thresholding(im, LICK_FRAME_THRESHOLD);

        if (nloop != 0) {
	    cv::absdiff(prevs, gray, thresh);
	    double pixel_sum_thresh = cv::sum(thresh)[0];
	    double pixel_sum_gray = cv::sum(gray)[0];
	    if (pixel_sum_thresh > LICK_SUM_THRESHOLD) {
	      std::cout << "DC1394: Lick" << std::endl;
	    }
	    if (fp_lick != NULL) {
                fwrite(&pixel_sum_thresh, sizeof(pixel_sum_thresh), 1, fp_lick);
	        fwrite(&pixel_sum_gray, sizeof(pixel_sum_gray), 1, fp_lick);
	    }
	}

	prevs = gray.clone();
	nloop++;
#endif
#ifdef STANDALONE
        if (key == 1048689 || key == 113 /*q*/) {
            std::cout << "DC1394: Mean frame rate was " << nframes/total_dur << " fps" << std::endl;
            pthread_cancel(acq_thread);
            pthread_cancel(save_thread);
            return 0;
        }
        if (key == 1048691 /*s*/) {
            fn = "";
            std::cout << "DC1394: Stopping video" << std::endl;
            ncount = 0;
        }
        if (key == 1048690 /*r*/) {
            fn = trunk + std::string("tmp/");
            std::cout << "DC1394: Starting video, writing to " << fn << std::endl;
            ncount = 0;
        }
#endif // #standalone
        clock_gettime( CLOCK_REALTIME, &time2);
        double loop_dur = tdiff(time2, time3);
        clock_gettime( CLOCK_REALTIME, &time3);
        double meanfps = 0;

        total_dur = tdiff(time3, time0);
        if (total_dur > 0)
            meanfps = nframes / total_dur;
        double currentfps = ret / loop_dur;
        std::cout << "DC1394: Current fps: " << std::setprecision(7) << currentfps
                  << " Average fps: " << std::setprecision(7) << meanfps << "\r" << std::flush;
#ifdef STANDALONE
        // std::cout << capture_dur << "\t" << target_dur << "\t" << rem << "\t" << loop_dur << std::endl;
#endif
    }

    if (d) {
        dc1394_free(d);
    }

#ifndef STANDALONE
    close(s);
#endif
    return 0;
}
