/* 2010-10-28
   C. Schmidt-Hieber, University College London */

#include <cstdio>
#include <iostream>
#include <iomanip>
#include <ctime>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/types.h>
#include <fcntl.h>
#include <sstream>
#include <algorithm>
#include <opencv2/opencv.hpp>

static const double BILLION = 1000000000L;
static const int BUFSIZE = 4096;
static const int WIDTH = 320;
static const int HEIGHT = 240;
static const int FPS = 30;
static const int CAM_ID = 2;
static const bool g_rotate = false;

double tdiff(timespec time1, timespec time0) {
    return ( time1.tv_sec - time0.tv_sec )
         + ( time1.tv_nsec - time0.tv_nsec ) / BILLION;
}

double t2d(timespec time1) {
    return time1.tv_sec + time1.tv_nsec / BILLION;
}

void write_send(int socket, const cv::Mat& im, CvVideoWriter* pWriter, int& ncount) {
    timespec time1;
    if( clock_gettime( CLOCK_REALTIME, &time1) == -1 ) {
        fprintf(stderr, "WEBCAM: clock gettime");
    }
    double dtime1 = t2d(time1);
    
    while (send(socket, &dtime1, sizeof(double), 0) < 0) {
        perror("WEBCAM: client: send");
    }
    IplImage ipl_im(im);
    cvWriteFrame(pWriter, &ipl_im);
    ncount++;
}

void get_image(cv::VideoCapture& camera, cv::Mat& im, const cv::Mat& mapping, bool rotate, int socket, CvVideoWriter* pWriter, int& ncount) {
    camera >> im;
    cv::Mat cpim = im.clone();
    if (rotate) {
        cv::warpAffine(cpim, im, mapping, im.size());
    }
    if (pWriter != NULL) {
        write_send(socket, im, pWriter, ncount);
    }
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
    
    cv::VideoCapture camera(CAM_ID);
    if (camera.isOpened()) {
        camera.release();
    }
    camera.open(CAM_ID);

    camera.set(CV_CAP_PROP_FRAME_WIDTH, WIDTH);
    camera.set(CV_CAP_PROP_FRAME_HEIGHT, HEIGHT);
    camera.set(CV_CAP_PROP_FPS, FPS);
    
    int width = camera.get(CV_CAP_PROP_FRAME_WIDTH);
    int height = camera.get(CV_CAP_PROP_FRAME_HEIGHT);
    std::cout << "WEBCAM: Initialized camera with " << width << "x" << height << std::endl;
#ifdef STANDALONE
    std::cout << "WEBCAM: fps " << camera.get(CV_CAP_PROP_FPS) << std::endl;
    std::cout << "WEBCAM: fourcc " << camera.get(CV_CAP_PROP_FOURCC) << std::endl;
    std::cout << "WEBCAM: Format " << camera.get(CV_CAP_PROP_FORMAT) << std::endl;
    std::cout << "WEBCAM: Mode " << camera.get(CV_CAP_PROP_MODE) << std::endl;
    std::cout << "WEBCAM: Brightness " << camera.get(CV_CAP_PROP_BRIGHTNESS) << std::endl;
    std::cout << "WEBCAM: Contrast " << camera.get(CV_CAP_PROP_CONTRAST) << std::endl;
    std::cout << "WEBCAM: Saturation " << camera.get(CV_CAP_PROP_SATURATION) << std::endl;
    std::cout << "WEBCAM: Hue " << camera.get(CV_CAP_PROP_HUE) << std::endl;
    std::cout << "WEBCAM: Gain " << camera.get(CV_CAP_PROP_GAIN) << std::endl;
    std::cout << "WEBCAM: Exposure " << camera.get(CV_CAP_PROP_EXPOSURE) << std::endl;
    std::cout << "WEBCAM: Convert to RGB " << camera.get(CV_CAP_PROP_CONVERT_RGB) << std::endl;
    // std::cout << "WEBCAM: White Balance " << camera.get(CV_CAP_PROP_WHITE_BALANCE) << std::endl;
#endif
    cv::Mat mapping = cv::getRotationMatrix2D(cv::Point2f(width/2.0, height/2.0), 180.0, 1.0);
    cv::namedWindow("Webcam");
    cvMoveWindow("Webcam", 1280-WIDTH, 0);
    cv::Mat im;
    int ncount = 0;
    get_image(camera, im, mapping, g_rotate, -1, false, ncount);
    cv::imshow("Webcam", im);
    
#ifndef STANDALONE
    int s;
    if ((s = socket(AF_UNIX, SOCK_STREAM, 0)) < 0) {
        perror("WEBCAM: server: socket");
        return -1;
    }

    /*
     * Create the address we will be connecting to.
     */
    sockaddr_un sa;
    sa.sun_family = AF_UNIX;

    std::ostringstream tmpfn;
    tmpfn << "vidsocket" << ntry;
    std::cout << "WEBCAM: socket name " << tmpfn.str() << std::endl;

    int nameLen = strlen(tmpfn.str().c_str());
    if (nameLen >= (int) sizeof(sa.sun_path) -1) { /* too long? */
        return -1;
    }
    
    sa.sun_path[0] = '\0';  /* abstract namespace */
    strcpy(sa.sun_path+1, tmpfn.str().c_str());
    int len = 1 + nameLen + offsetof(struct sockaddr_un, sun_path);

    // sockaddr_un sa;

    // std::string tmpfn("vidsocket");
    
    // int nameLen = strlen(tmpfn.c_str());
    // if (nameLen >= (int) sizeof(sa.sun_path) -1)  /* too long? */
    //     return -1;

    // sa.sun_family = AF_UNIX;
    // sa.sun_path[0] = '\0';  /* abstract namespace */
    // strcpy(sa.sun_path+1, tmpfn.c_str());

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

    if (connect(s, (sockaddr*)&sa, len) < 0) {
        perror("WEBCAM: client: connect");
        return -1;
    }

    bool connected = false;
    std::vector<char> data(BUFSIZE);
    int nrec = recv(s, &data[0], data.size(), 0);
    std::string datastr(data.begin(), data.end());
    if (nrec<=0) {
        std::cerr << "WEBCAM: Didn't receive start message; exiting now" << std::endl;
        return -1;
    }
    connected = true;
    
    std::string ready = "ready";
    while (send(s, ready.c_str(), ready.size(), 0) < 0) {
        perror("WEBCAM: client: send");
    }

    int flags;
    if (-1 == (flags = fcntl(s, F_GETFL, 0)))
        flags = 0;

    if (fcntl(s, F_SETFL, flags | O_NONBLOCK)==-1) {
        perror("WEBCAM: client: unblock");
    }
#endif

    CvVideoWriter* pWriter = NULL;
    
    timespec time0;
    if( clock_gettime( CLOCK_REALTIME, &time0) == -1 ) {
        fprintf(stderr, "WEBCAM: clock gettime");
    }
    timespec time1 = time0;
    timespec time2 = time0;
    timespec time3 = time0;
    timespec t_disconnect = time0;
    int nframes = 0;

#ifdef STANDALONE
    int s = -1;
    std::string fn = "";
#else
    std::string fn = "";
#endif
    while (true) {
        if( clock_gettime( CLOCK_REALTIME, &time1) == -1 ) {
            fprintf(stderr, "WEBCAM: clock gettime");
        }
#ifndef STANDALONE
        std::vector<char> data(BUFSIZE, '\0');
        int nrec = recv(s, &data[0], data.size(), 0);
        std::string datastr(data.begin(), data.end());
#endif
        get_image(camera, im, mapping, g_rotate, s, pWriter, ncount);

        cv::imshow("Webcam", im);

        if( clock_gettime( CLOCK_REALTIME, &time2) == -1 ) {
            fprintf(stderr, "WEBCAM: clock gettime");
        }
        double capture_dur = tdiff(time2, time1);
        double rem = target_dur - capture_dur;
        if (rem > tol) {
            nframes += 1;
        } else {
            int dropped_frames = int((capture_dur+tol)/target_dur);
            nframes += dropped_frames +1;
            for (int nf = 0; nf < dropped_frames; ++nf) {
                if (pWriter != NULL) {
                    write_send(s, im, pWriter, ncount);
                }
            }
        }
        double next_timestamp = (nframes * target_dur) + t2d(time0);
        
        if( clock_gettime( CLOCK_REALTIME, &time3) == -1 ) {
            fprintf(stderr, "WEBCAM: clock gettime");
        }
        double total_wait = next_timestamp -  t2d(time3);
        while (total_wait < tol) {
            total_wait += target_dur;
            nframes++;
            if (pWriter != NULL) {
                write_send(s, im, pWriter, ncount);
            }
        }

        int key = cv::waitKey(int(1e3*total_wait));

        while (key != -1) {
            next_timestamp = (nframes * target_dur) + t2d(time0);
            if( clock_gettime( CLOCK_REALTIME, &time3) == -1 ) {
                fprintf(stderr, "WEBCAM: clock gettime");
            }
            if (t2d(time3) < next_timestamp) {
                total_wait = next_timestamp - t2d(time3);
            } else {
                if (pWriter != NULL)
                    cvReleaseVideoWriter(&pWriter);
                
                exit(0);
            }
            key = cv::waitKey(int(1e3*total_wait));
        }

#ifndef STANDALONE
        
        // no update from blender in a long time, terminate process
        if (datastr.find("1")==std::string::npos) {
            if (connected) {
                t_disconnect = time1;
                connected = false;
            } else {
                if (tdiff(time1, t_disconnect) > 0.5) {
                    std::cout << "WEBCAM: Received termination signal" << std::endl;
                    if (pWriter != NULL)
                        cvReleaseVideoWriter(&pWriter);
                    return 0;
                }
            }
        } else {
            connected = true;
        }

        // Stop recording
        if (datastr.find("stop") != std::string::npos && pWriter != NULL) {
            cvReleaseVideoWriter(&pWriter);
            pWriter = NULL;
            std::cout << "WEBCAM: Stopping video" << std::endl;
            connected = true;
            ncount = 0;
        }

        // Start recording
        if (datastr.find("avi") != std::string::npos && datastr.find("stop") == std::string::npos && pWriter == NULL) {
            std::size_t startpos = datastr.find("begin")+5; 
            std::size_t endpos = datastr.find("end") - datastr.find("begin") - 5; 
            fn = datastr.substr(startpos, endpos);
            std::cout << "WEBCAM: Starting video, writing to " << fn << std::endl;
            pWriter = cvCreateVideoWriter( fn.c_str(), CV_FOURCC('F', 'M', 'P', '4'), fps, cvSize(width, height),
                                           1);
            connected = true;
            ncount = 0;
        }
#endif
    }
    if (pWriter != NULL)
        cvReleaseVideoWriter(&pWriter);
    return 0;
}
