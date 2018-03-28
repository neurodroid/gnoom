/* Based on https://github.com/AravisProject/aravis/raw/master/tests/arvcameratest.c
 * The original file is released under the LGPL v2+ as part of Aravis
 *
 * Modified by Christoph Schmidt-Hieber to communicate via sockets
 * 2018-03-24
 */

#include <arv.h>
#include <stdlib.h>
#include <signal.h>
#include <stdio.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <fcntl.h>
#include <sstream>
#include <iostream>
#include <vector>
#include <boost/filesystem.hpp>

#define SOCKTYPE AF_UNIX

static const int BUFSIZE = 4096;
static const double BILLION = 1000000000L;
static const char* trunk = "";
static const double TIMEOUT = 2.0;
static char *arv_option_camera_name = NULL;
static char *arv_option_debug_domains = NULL;
static gboolean arv_option_snaphot = FALSE;
static char *arv_option_trigger = NULL;
static double arv_option_software_trigger = -1;
static double arv_option_frequency = -1.0;
static int arv_option_width = -1;
static int arv_option_height = -1;
static int arv_option_xoff = -1;
static int arv_option_yoff = -1;
static int arv_option_horizontal_binning = -1;
static int arv_option_vertical_binning = -1;
static double arv_option_exposure_time_us = -1;
static int arv_option_gain = -1;
static gboolean arv_option_auto_socket_buffer = FALSE;
static gboolean arv_option_no_packet_resend = FALSE;
static double arv_option_packet_request_ratio = -1.0;
static unsigned int arv_option_packet_timeout = 20;
static unsigned int arv_option_frame_retention = 100;
static int arv_option_gv_stream_channel = -1;
static int arv_option_gv_packet_delay = -1;
static int arv_option_gv_packet_size = -1;
static gboolean arv_option_realtime = FALSE;
static gboolean arv_option_high_priority = FALSE;
static gboolean arv_option_no_packet_socket = FALSE;
static char *arv_option_chunks = NULL;
static unsigned int arv_option_bandwidth_limit = -1;

static const GOptionEntry arv_option_entries[] =
{
	{
		"name",					'n', 0, G_OPTION_ARG_STRING,
		&arv_option_camera_name,		"Camera name", NULL
	},
	{
		"snapshot",				's', 0, G_OPTION_ARG_NONE,
		&arv_option_snaphot,			"Snapshot", NULL
	},
	{
		"frequency", 				'f', 0, G_OPTION_ARG_DOUBLE,
		&arv_option_frequency,			"Acquisition frequency", NULL
	},
	{
		"trigger",				't', 0, G_OPTION_ARG_STRING,
		&arv_option_trigger,			"External trigger", NULL
	},
	{
		"software-trigger",			'o', 0, G_OPTION_ARG_DOUBLE,
		&arv_option_software_trigger,		"Emit software trigger", NULL
	},
	{
		"width", 				'w', 0, G_OPTION_ARG_INT,
		&arv_option_width,			"Width", NULL
	},
	{
		"height", 				'h', 0, G_OPTION_ARG_INT,
		&arv_option_height, 			"Height", NULL
	},
	{
	       "h-binning", 				'\0', 0, G_OPTION_ARG_INT,
		&arv_option_horizontal_binning,		"Horizontal binning", NULL
	},
	{
		"v-binning", 				'\0', 0, G_OPTION_ARG_INT,
		&arv_option_vertical_binning, 		"Vertical binning", NULL
	},
	{
		"exposure", 				'e', 0, G_OPTION_ARG_DOUBLE,
		&arv_option_exposure_time_us, 		"Exposure time (µs)", NULL
	},
	{
		"gain", 				'g', 0, G_OPTION_ARG_INT,
		&arv_option_gain,	 		"Gain (dB)", NULL
	},
	{
		"auto",					'a', 0, G_OPTION_ARG_NONE,
		&arv_option_auto_socket_buffer,		"Auto socket buffer size", NULL
	},
	{
		"no-packet-resend",			'r', 0, G_OPTION_ARG_NONE,
		&arv_option_no_packet_resend,		"No packet resend", NULL
	},
	{
		"packet-request-ratio",			'q', 0, G_OPTION_ARG_DOUBLE,
		&arv_option_packet_request_ratio,	"Packet resend request limit as a frame packet number ratio [0..2.0]", NULL
	},
	{
		"packet-timeout", 			'p', 0, G_OPTION_ARG_INT,
		&arv_option_packet_timeout, 		"Packet timeout (ms)", NULL
	},
	{
		"frame-retention", 			'm', 0, G_OPTION_ARG_INT,
		&arv_option_frame_retention, 		"Frame retention (ms)", NULL
	},
	{
		"gv-stream-channel",			'c', 0, G_OPTION_ARG_INT,
		&arv_option_gv_stream_channel,		"GigEVision stream channel id", NULL
	},
	{
		"gv-packet-delay",			'y', 0, G_OPTION_ARG_INT,
		&arv_option_gv_packet_delay,		"GigEVision packet delay (ns)", NULL
	},
	{
		"gv-packet-size",			'i', 0, G_OPTION_ARG_INT,
		&arv_option_gv_packet_size,		"GigEVision packet size (bytes)", NULL
	},
	{
		"chunks", 				'u', 0, G_OPTION_ARG_STRING,
		&arv_option_chunks,	 		"Chunks", NULL
	},
	{
		"realtime",				'\0', 0, G_OPTION_ARG_NONE,
		&arv_option_realtime,			"Make stream thread realtime", NULL
	},
	{
		"high-priority",			'\0', 0, G_OPTION_ARG_NONE,
		&arv_option_high_priority,		"Make stream thread high priority", NULL
	},
	{
		"no-packet-socket",			'\0', 0, G_OPTION_ARG_NONE,
		&arv_option_no_packet_socket,		"Disable use of packet socket", NULL
	},
	{
		"debug", 				'd', 0, G_OPTION_ARG_STRING,
		&arv_option_debug_domains, 		"Debug domains", NULL
	},
	{
		"bandwidth-limit",			'b', 0, G_OPTION_ARG_INT,
		&arv_option_bandwidth_limit,		"Desired USB3 Vision device bandwidth limit", NULL
	},
	{ NULL }
};

typedef struct {
	GMainLoop *main_loop;
        int buffer_count;
        int width;
        int height;
	int ipcs;
	ArvChunkParser *chunk_parser;
        ArvCamera *camera;
        char **chunks;
        FILE* rawfile;
        FILE* trawfile;
        timespec t_last_connect;
} ApplicationData;

static gboolean cancel = FALSE;

static void
set_cancel (int signal)
{
	cancel = TRUE;
}

double tdiff(timespec time1, timespec time0) {
    return ( time1.tv_sec - time0.tv_sec )
         + ( time1.tv_nsec - time0.tv_nsec ) / BILLION;
}

double t2d(timespec time1) {
    return time1.tv_sec + time1.tv_nsec / BILLION;
}

void
write_send(ApplicationData* data) {
}

static gboolean
keep_conn_cb(void *abstract_data) {

        ApplicationData *data = static_cast<ApplicationData*>(abstract_data);

        std::vector<char> ipcdata(BUFSIZE);
        int nrec = recv(data->ipcs, &ipcdata[0], ipcdata.size(), 0);
        std::string datastr(ipcdata.begin(), ipcdata.end());

	/* Explicit termination */
        if (datastr.find("quit")!=std::string::npos) {
            std::cout << "USB3: Game over signal." << std::endl;
            std::string sclose = "close";
            while (send(data->ipcs, sclose.c_str(), sclose.size(), 0) < 0) {
                perror("USB3: client: send");
            }
	    cancel = TRUE;
            return FALSE;
        }

        if (datastr.compare(0, 1, "1") == 0) {
            clock_gettime(CLOCK_REALTIME, &data->t_last_connect);
	} else {
            if (cancel == FALSE) {
                timespec t_disconnect;
                clock_gettime(CLOCK_REALTIME, &t_disconnect);
                if (tdiff(t_disconnect, data->t_last_connect) > TIMEOUT) {
                    std::cout << "USB3: Connection timeout" << std::endl;
                    cancel = TRUE;
                }
            }
        }

        // Stop recording
        if (datastr.find("stop") != std::string::npos && data->rawfile != NULL) {
            fclose(data->rawfile);
            fclose(data->trawfile);
            data->rawfile = NULL;
            data->trawfile = NULL;
            std::cout << "USB3: Stopping video" << std::endl;
        }
        
        // Start recording
        if (datastr.find("avi") != std::string::npos &&
            datastr.find("stop") == std::string::npos && data->rawfile == NULL) {
            std::size_t startpos = datastr.find("begin")+5;
            std::size_t endpos = datastr.find("end") - datastr.find("begin") - 5; 
            std::string fn = datastr.substr(startpos, endpos);
            fn = std::string(trunk) + fn;
            boost::filesystem::path path(fn);
            boost::filesystem::path writepath(path);

            // Test whether dir exists:
            if (!boost::filesystem::exists(writepath)) {
                std::cout << "USB3: Creating directory " << writepath << std::endl;
                boost::filesystem::create_directories(writepath);
            }
            fn += "/raw";

            std::cout << "USB3: Starting video, writing to " << fn << std::endl;

            data->rawfile = fopen(fn.c_str(), "wb");
            data->trawfile = fopen((fn + "times").c_str(), "wb");
            double dwidth = (double)data->width;
            double dheight = (double)data->height;
            fwrite(&dwidth, 1, sizeof(double), data->trawfile);
            fwrite(&dheight, 1, sizeof(double), data->trawfile);
        }
        return TRUE;

}

static void
new_buffer_cb (ArvStream *stream, ApplicationData *data)
{

	ArvBuffer *buffer;

	buffer = arv_stream_try_pop_buffer (stream);
	if (buffer != NULL) {
            if (arv_buffer_get_status (buffer) == ARV_BUFFER_STATUS_SUCCESS) {
			data->buffer_count++;
                        if (data->rawfile != NULL) {
                            timespec time1;
                            clock_gettime( CLOCK_REALTIME, &time1);
                            double dtime1 = t2d(time1);
    
                            if (send(data->ipcs, &dtime1, sizeof(double), 0) < 0) {
                                perror("USB3: client: send");
                            }
                            size_t bsize;
                            const void* bdata = arv_buffer_get_data(buffer, &bsize);
                            fwrite(bdata, bsize, sizeof(char), data->rawfile);
                            fwrite(&dtime1, 1, sizeof(double), data->trawfile);
                        }
            }
		if (arv_buffer_get_payload_type (buffer) == ARV_BUFFER_PAYLOAD_TYPE_CHUNK_DATA &&
		    data->chunks != NULL) {
			int i;

			for (i = 0; data->chunks[i] != NULL; i++)
				printf ("USB3: %s = %" G_GINT64_FORMAT "\n", data->chunks[i],
					arv_chunk_parser_get_integer_value (data->chunk_parser, buffer, data->chunks[i]));
		}

		arv_stream_push_buffer (stream, buffer);
	}
}

static void
stream_cb (void *user_data, ArvStreamCallbackType type, ArvBuffer *buffer)
{
	if (type == ARV_STREAM_CALLBACK_TYPE_INIT) {
		if (arv_option_realtime) {
			if (!arv_make_thread_realtime (10))
				printf ("USB3: Failed to make stream thread realtime\n");
		} else if (arv_option_high_priority) {
			if (!arv_make_thread_high_priority (-10))
				printf ("USB3: Failed to make stream thread high priority\n");
		}
	}
}

static gboolean
periodic_task_cb (void *abstract_data)
{
	ApplicationData *data = static_cast<ApplicationData*>(abstract_data);

	if (data->buffer_count == 0) {
	  cancel = TRUE;
	}

	printf ("USB3: Frame rate = %d Hz\n", data->buffer_count);
	data->buffer_count = 0;
	
	if (cancel) {
            g_main_loop_quit (data->main_loop);
            if (data->rawfile != NULL) {
                fclose(data->rawfile);
                fclose(data->trawfile);
                data->rawfile = NULL;
                data->trawfile = NULL;
            }
            close(data->ipcs);
            return FALSE;
	}

	return TRUE;
}

static gboolean
emit_software_trigger (void *abstract_data)
{
	ArvCamera *camera = static_cast<ArvCamera*>(abstract_data);

	arv_camera_software_trigger (camera);

	return TRUE;
}

static void
control_lost_cb (ArvGvDevice *gv_device)
{
	printf ("USB3: Control lost\n");

	cancel = TRUE;
}

int
init_socket()
{
    timespec t_sleep, t_rem;
    t_sleep.tv_sec = 0;
    t_sleep.tv_nsec = 10;

    int ipcs;
    if ((ipcs = socket(SOCKTYPE, SOCK_STREAM, 0)) < 0) {
        perror("USB3: client: socket");
	return -1;
    }

    sockaddr_un sa;
    sa.sun_family = SOCKTYPE;

    std::ostringstream tmpfn;
    char* ntry = (char*)"0";
    tmpfn << "usb3socket" << ntry;
    std::cout << "USB3: socket name " << tmpfn.str() << std::endl;
    
    int nameLen = strlen(tmpfn.str().c_str());
    if (nameLen >= (int) sizeof(sa.sun_path) -1) { /* too long? */
        return -1;
    }
    
    sa.sun_path[0] = '\0';  /* abstract namespace */
    strcpy(sa.sun_path+1, tmpfn.str().c_str());
    int len = 1 + nameLen + offsetof(struct sockaddr_un, sun_path);

    std::cout << "USB3: Waiting for connection... " << std::flush;
    while (true) {
        // wait for connection:
        if (connect(ipcs, (sockaddr*)&sa, len) < 0) {
            nanosleep(&t_sleep, &t_rem);
        } else {
            break;
        }
    }
    std::cout << "done" << std::endl;
    return ipcs;
}

int
init_connection(int ipcs) {
    bool connected = false;
    std::vector<char> ipcdata(BUFSIZE);
    int nrec = recv(ipcs, &ipcdata[0], ipcdata.size(), 0);
    std::string ipcdatastr(ipcdata.begin(), ipcdata.end());
    if (nrec<=0) {
        std::cerr << "USB3: Didn't receive start message; exiting now" << std::endl;
	close(ipcs);
        return -1;
    }
    connected = true;
    
    std::string ready = "ready";
    while (send(ipcs, ready.c_str(), ready.size(), 0) < 0) {
        perror("USB3: client: send");
        close(ipcs);
	return -1;
    }
    int flags = 0;
    if (-1 == (flags = fcntl(ipcs, F_GETFL, 0)))
        flags = 0;

    if (fcntl(ipcs, F_SETFL, flags | O_NONBLOCK)==-1) {
        perror("USB3: client: unblock");
        close(ipcs);
	return -1;
    }
    return 0;
}

int
main (int argc, char **argv)
{
	ApplicationData data;
	ArvStream *stream;
	GOptionContext *context;
	GError *error = NULL;
	int i;

	data.ipcs = init_socket();
	if (data.ipcs < 0) {
		return EXIT_FAILURE;
	}
	if (init_connection(data.ipcs) < 0) {
		return EXIT_FAILURE;
	}
	data.buffer_count = 0;
	data.chunks = NULL;
	data.chunk_parser = NULL;
        data.rawfile = NULL;
        data.trawfile = NULL;
        clock_gettime(CLOCK_REALTIME, &data.t_last_connect);
	arv_g_thread_init (NULL);
	arv_g_type_init ();

	context = g_option_context_new (NULL);
	g_option_context_add_main_entries (context, arv_option_entries, NULL);

	if (!g_option_context_parse (context, &argc, &argv, &error)) {
		g_option_context_free (context);
		g_print ("Option parsing failed: %s\n", error->message);
		g_error_free (error);
		return EXIT_FAILURE;
	}

	g_option_context_free (context);

	arv_debug_enable (arv_option_debug_domains);

	if (arv_option_camera_name == NULL)
		g_print ("Looking for the first available camera\n");
	else
		g_print ("Looking for camera '%s'\n", arv_option_camera_name);

	data.camera = arv_camera_new (arv_option_camera_name);
	if (data.camera != NULL) {
		void (*old_sigint_handler)(int);
		gint payload;
		gint x, y;
		gint dx, dy;
		double exposure;
		guint64 n_completed_buffers;
		guint64 n_failures;
		guint64 n_underruns;
		int gain;
		guint software_trigger_source = 0;

		if (arv_option_chunks != NULL) {
			char *striped_chunks;

			striped_chunks = g_strdup (arv_option_chunks);
			arv_str_strip (striped_chunks, " ,:;", ',');
			data.chunks = g_strsplit_set (striped_chunks, ",", -1);
			g_free (striped_chunks);

			data.chunk_parser = arv_camera_create_chunk_parser (data.camera);

			for (i = 0; data.chunks[i] != NULL; i++) {
				char *chunk = g_strdup_printf ("USB3: Chunk%s", data.chunks[i]);

				g_free (data.chunks[i]);
				data.chunks[i] = chunk;
			}
		}

		arv_camera_set_chunks (data.camera, arv_option_chunks);
		arv_camera_set_region (data.camera, arv_option_xoff, arv_option_yoff, arv_option_width, arv_option_height);
		arv_camera_set_binning (data.camera, arv_option_horizontal_binning, arv_option_vertical_binning);
		arv_camera_set_exposure_time (data.camera, arv_option_exposure_time_us);
		arv_camera_set_gain (data.camera, arv_option_gain);

		if (arv_camera_is_uv_device(data.camera)) {
			arv_camera_uv_set_bandwidth (data.camera, arv_option_bandwidth_limit);
		}

		if (arv_camera_is_gv_device (data.camera)) {
			arv_camera_gv_select_stream_channel (data.camera, arv_option_gv_stream_channel);
			arv_camera_gv_set_packet_delay (data.camera, arv_option_gv_packet_delay);
			arv_camera_gv_set_packet_size (data.camera, arv_option_gv_packet_size);
			arv_camera_gv_set_stream_options (data.camera, arv_option_no_packet_socket ?
							  ARV_GV_STREAM_OPTION_PACKET_SOCKET_DISABLED :
							  ARV_GV_STREAM_OPTION_NONE);
		}

		arv_camera_get_region (data.camera, &x, &y, &data.width, &data.height);
		arv_camera_get_binning (data.camera, &dx, &dy);
		exposure = arv_camera_get_exposure_time (data.camera);
		payload = arv_camera_get_payload (data.camera);
		gain = arv_camera_get_gain (data.camera);

		printf ("USB3: vendor name           = %s\n", arv_camera_get_vendor_name (data.camera));
		printf ("USB3: model name            = %s\n", arv_camera_get_model_name (data.camera));
		printf ("USB3: device id             = %s\n", arv_camera_get_device_id (data.camera));
		printf ("USB3: image x offset        = %d\n", x);
		printf ("USB3: image y offset        = %d\n", y);
		printf ("USB3: image width           = %d\n", data.width);
		printf ("USB3: image height          = %d\n", data.height);
		printf ("USB3: horizontal binning    = %d\n", dx);
		printf ("USB3: vertical binning      = %d\n", dy);
		printf ("USB3: payload               = %d bytes\n", payload);
		printf ("USB3: exposure              = %g µs\n", exposure);
		printf ("USB3: gain                  = %d dB\n", gain);

		if (arv_camera_is_gv_device (data.camera)) {
			printf ("USB3: gv n_stream channels  = %d\n", arv_camera_gv_get_n_stream_channels (data.camera));
			printf ("USB3: gv current channel    = %d\n", arv_camera_gv_get_current_stream_channel (data.camera));
			printf ("USB3: gv packet delay       = %" G_GINT64_FORMAT " ns\n", arv_camera_gv_get_packet_delay (data.camera));
			printf ("USB3: gv packet size        = %d bytes\n", arv_camera_gv_get_packet_size (data.camera));
		}

		if (arv_camera_is_uv_device (data.camera)) {
			guint min,max;

			arv_camera_uv_get_bandwidth_bounds (data.camera, &min, &max);
			printf ("USB3: uv bandwidth limit     = %d [%d..%d]\n", arv_camera_uv_get_bandwidth (data.camera), min, max);
		}

		stream = arv_camera_create_stream (data.camera, stream_cb, NULL);
		if (stream != NULL) {
			if (ARV_IS_GV_STREAM (stream)) {
				if (arv_option_auto_socket_buffer)
					g_object_set (stream,
						      "socket-buffer", ARV_GV_STREAM_SOCKET_BUFFER_AUTO,
						      "socket-buffer-size", 0,
						      NULL);
				if (arv_option_no_packet_resend)
					g_object_set (stream,
						      "packet-resend", ARV_GV_STREAM_PACKET_RESEND_NEVER,
						      NULL);
				if (arv_option_packet_request_ratio >= 0.0)
					g_object_set (stream,
						      "packet-request-ratio", arv_option_packet_request_ratio,
						      NULL);

				g_object_set (stream,
					      "packet-timeout", (unsigned) arv_option_packet_timeout * 1000,
					      "frame-retention", (unsigned) arv_option_frame_retention * 1000,
					      NULL);
			}

			for (i = 0; i < 50; i++)
				arv_stream_push_buffer (stream, arv_buffer_new (payload, NULL));

			arv_camera_set_acquisition_mode (data.camera, ARV_ACQUISITION_MODE_CONTINUOUS);

			if (arv_option_frequency > 0.0)
				arv_camera_set_frame_rate (data.camera, arv_option_frequency);

			if (arv_option_trigger != NULL)
				arv_camera_set_trigger (data.camera, arv_option_trigger);

			if (arv_option_software_trigger > 0.0) {
				arv_camera_set_trigger (data.camera, "Software");
				software_trigger_source = g_timeout_add ((double) (0.5 + 1000.0 /
										   arv_option_software_trigger),
									 emit_software_trigger, data.camera);
			}

			arv_camera_start_acquisition (data.camera);

			g_signal_connect (stream, "new-buffer", G_CALLBACK (new_buffer_cb), &data);
			arv_stream_set_emit_signals (stream, TRUE);

			g_signal_connect (arv_camera_get_device (data.camera), "control-lost",
					  G_CALLBACK (control_lost_cb), NULL);

			g_timeout_add_seconds (1, periodic_task_cb, &data);

                        g_idle_add (keep_conn_cb, &data);

			data.main_loop = g_main_loop_new (NULL, FALSE);

			old_sigint_handler = signal (SIGINT, set_cancel);

			g_main_loop_run (data.main_loop);

			if (software_trigger_source > 0)
				g_source_remove (software_trigger_source);

			signal (SIGINT, old_sigint_handler);

			g_main_loop_unref (data.main_loop);

			arv_stream_get_statistics (stream, &n_completed_buffers, &n_failures, &n_underruns);

			printf ("USB3: Completed buffers = %Lu\n", (unsigned long long) n_completed_buffers);
			printf ("USB3: Failures          = %Lu\n", (unsigned long long) n_failures);
			printf ("USB3: Underruns         = %Lu\n", (unsigned long long) n_underruns);

			arv_camera_stop_acquisition (data.camera);

			arv_stream_set_emit_signals (stream, FALSE);

			g_object_unref (stream);
		} else
			printf ("USB3: Can't create stream thread (check if the device is not already used)\n");

		g_object_unref (data.camera);
	} else
		printf ("USB3: No camera found\n");

	if (data.chunks != NULL)
		g_strfreev (data.chunks);

	g_clear_object (&data.chunk_parser);

	return 0;
}
