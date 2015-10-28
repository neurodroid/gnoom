/* 2010-10-28
   C. Schmidt-Hieber, University College London */

#include "dc1394.h"
#include "dc1394cam.h"

#include <iostream>
#include <sstream>
#include <dc1394/dc1394.h>
#include <dc1394/vendor/avt.h>

#include <cstdlib>
#include <cstring>
#include <poll.h>

void cleanup_and_exit(dc1394cam& camera) {
    camera.free();
    exit(1);
}

dc1394cam::dc1394cam() :
    m_cam(0),
    m_video_mode((dc1394video_mode_t)0),
    m_fdcam(0),
    m_mingain(0), m_maxgain(0),
    is_transmitting(false),
    is_capturing(false)
{}

dc1394cam::dc1394cam(dc1394_t *d, uint64_t guid) :
    m_cam(0),
    m_video_mode((dc1394video_mode_t)0),
    m_fdcam(0),
    m_mingain(0), m_maxgain(0),
    is_transmitting(false),
    is_capturing(false)
{
    init(d, guid);
}

dc1394cam::~dc1394cam() {
    free();
}

void dc1394cam::free() {
    if (m_cam) {
        std::cout << "DC1394CAM: Releasing camera... ";
        if (is_capturing) {
            dc1394_capture_stop(m_cam);
            is_capturing = false;
        }
        if (is_transmitting) {
            dc1394_video_set_transmission(m_cam, DC1394_OFF);
            is_transmitting = false;
        }
        dc1394_camera_free(m_cam);
        std::cout << "done" << std::endl;
    }
}

dc1394error_t dc1394cam::start_transmission() {
    is_transmitting = true;
    return dc1394_video_set_transmission(m_cam, DC1394_ON);
}

dc1394error_t dc1394cam::start_capture() {
    dc1394_capture_stop(m_cam);
    dc1394error_t err = dc1394_video_set_transmission(m_cam, DC1394_OFF);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not stop transmission");

    err = dc1394_capture_setup(m_cam, NUMBUFS, DC1394_CAPTURE_FLAGS_CHANNEL_ALLOC);
    return err;
}

dc1394camera_t* dc1394cam::cam() {return m_cam;}

int dc1394cam::init(dc1394_t *d, uint64_t guid) {
    m_cam = dc1394_camera_new(d, guid);
    if (!m_cam) {
        dc1394_log_error("Failed to initialize camera");
        exit(1);
    }

    if(m_cam->vendor_id != DC1394_AVT_VENDOR_ID) {
        std::cout << "DC1394CAM: Will only work with AVT cameras" << std::endl;
        cleanup_and_exit(*this);
    }

    /*-----------------------------------------------------------------------
     *  get the best video mode and highest framerate. This can be skipped
     *  if you already know which mode/framerate you want...
     *-----------------------------------------------------------------------*/
    // set mode to FireWire 800:
    dc1394error_t err = dc1394_video_set_operation_mode(m_cam, DC1394_OPERATION_MODE_1394B);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not set operation mode to 1394b (FireWire 800)");

    err=dc1394_video_set_iso_speed(m_cam, DC1394_ISO_SPEED_800);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not set iso speed");

    // set extented (sic!) shutter time:
    err = dc1394_avt_set_extented_shutter(m_cam, 7500);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't set shutter time");
    
    // get video modes:
    dc1394video_modes_t video_modes;
    err=dc1394_video_get_supported_modes(m_cam,&video_modes);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't get video modes");

    // select highest res mode:
    dc1394color_coding_t coding;
    if (WIDTH==640) {
	int i=0;
	for (i=video_modes.num-1;i>=0;i--) {
	  if (!dc1394_is_video_mode_scalable(video_modes.modes[i])) {
		dc1394_get_color_coding_from_video_mode(m_cam,video_modes.modes[i], &coding);
		if (coding==DC1394_COLOR_CODING_MONO8) {
		    uint32_t uiwidth = 0;
		    uint32_t uiheight = 0;
		    dc1394_get_image_size_from_video_mode(m_cam, video_modes.modes[i], &uiwidth, &uiheight);
		    if (uiwidth==WIDTH) {
			m_video_mode=video_modes.modes[i];
			break;
		    }
		}
	    }
	}
	if (i < 0) {
	    dc1394_log_error("Could not get a valid MONO8 mode");
	    return 0;
	}
    } else {
        m_video_mode = DC1394_VIDEO_MODE_FORMAT7_0;
    }

    err=dc1394_get_color_coding_from_video_mode(m_cam, m_video_mode,&coding);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not get color coding");

    /*-----------------------------------------------------------------------
     *  setup capture
     *-----------------------------------------------------------------------*/
    err=dc1394_video_set_mode(m_cam, m_video_mode);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not set video mode");

    // get highest framerate
    if (WIDTH==640) {
        dc1394framerates_t framerates;
        err=dc1394_video_get_supported_framerates(m_cam, m_video_mode, &framerates);
        DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not get framerates");
        dc1394framerate_t framerate = framerates.framerates[framerates.num-1];
        err=dc1394_video_set_framerate(m_cam, DC1394_FRAMERATE_120);
        DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not set framerate");
    } else {
        err=dc1394_format7_set_roi(m_cam, m_video_mode, coding, DC1394_USE_MAX_AVAIL,
                                   uint32_t((640-WIDTH)/2), 
                                   uint32_t((480-HEIGHT)/2), 
				   WIDTH, HEIGHT);
        DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not set ROI");
    }

    err = start_capture();
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Could not setup camera-\nmake sure that the video mode and framerate are\nsupported by your camera");

    m_fdcam = dc1394_capture_get_fileno(m_cam);

    /*-----------------------------------------------------------------------
     *  set gain
     *-----------------------------------------------------------------------*/
    err = dc1394_feature_set_value(m_cam, DC1394_FEATURE_GAIN, 639);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't set gain");

    err = dc1394_feature_get_boundaries(m_cam, DC1394_FEATURE_GAIN, &m_mingain, &m_maxgain);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this), "Can't get gain limits");
    
#if 0
    // set gain to auto
    err = dc1394_feature_set_mode(m_cam, DC1394_FEATURE_GAIN, DC1394_FEATURE_MODE_AUTO);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't set autogain");

    err = dc1394_avt_set_auto_gain(m_cam, 0, 630);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't set autogain range");
#endif

    /*-----------------------------------------------------------------------
     *  set trigger
     *-----------------------------------------------------------------------*/
#if 1 //ndef STANDALONE
    err = dc1394_software_trigger_set_power(m_cam, DC1394_OFF);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't switch off software trigger");

    err = dc1394_external_trigger_set_power(m_cam, DC1394_ON);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't switch on external trigger");

    std::cout << "DC1394CAM: Operating in external trigger mode" << std::endl;

    err = dc1394_external_trigger_set_polarity(m_cam, DC1394_TRIGGER_ACTIVE_HIGH);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't set trigger polarity");

    dc1394trigger_mode_t mode;
    err = dc1394_external_trigger_get_mode(m_cam, &mode);
    std::cout << "DC1394CAM: Trigger mode was " << mode << std::endl;

    err = dc1394_external_trigger_set_mode(m_cam, DC1394_TRIGGER_MODE_0);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't set trigger polarity");

#else
    err = dc1394_software_trigger_set_power(m_cam, DC1394_ON);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't switch on software trigger");

    err = dc1394_external_trigger_set_power(m_cam, DC1394_OFF);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't switch off external trigger");

    err = dc1394_external_trigger_set_polarity(m_cam, DC1394_TRIGGER_ACTIVE_HIGH);
    DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this),"Can't set trigger polarity");

#endif    

#ifdef STANDALONE
    /*-----------------------------------------------------------------------
     *  report camera's features
     *-----------------------------------------------------------------------*/
    // read smart AVT feature capabilities
    dc1394_avt_smart_feature_info_t smartFeatureInquiry;
    if(m_cam->vendor_id == DC1394_AVT_VENDOR_ID) {
        err = dc1394_avt_get_smart_feature_inquiry( m_cam, &smartFeatureInquiry, sizeof(dc1394_avt_smart_feature_info_t) );
        DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this), "Couldn't read advanced AVT features");
        dc1394_avt_print_smart_features(&smartFeatureInquiry);        
    } else {
        memset( &smartFeatureInquiry, 0, sizeof(dc1394_avt_smart_feature_info_t) );
    }

    // read advanced AVT feature capabilities
    dc1394_avt_adv_feature_info_t advancedFeatureInquiry;
    if(m_cam->vendor_id == DC1394_AVT_VENDOR_ID) {
        err = dc1394_avt_get_advanced_feature_inquiry( m_cam, &advancedFeatureInquiry);
        DC1394_ERR_CLN_RTN(err,cleanup_and_exit(*this), "Couldn't read advanced AVT features");
        dc1394_avt_print_advanced_feature(&advancedFeatureInquiry);        
    } else {
        memset( &advancedFeatureInquiry, 0, sizeof(dc1394_avt_adv_feature_info_t) );
    }

    dc1394featureset_t features;
    err=dc1394_feature_get_all(m_cam, &features);
    if (err!=DC1394_SUCCESS) {
        dc1394_log_warning("Could not get feature set");
    }
    else {
        dc1394_feature_print_all(&features, stdout);
    }
#endif
}

void dc1394cam::get_image_size(uint32_t* width, uint32_t* height) const {
    dc1394_get_image_size_from_video_mode(m_cam, m_video_mode, width, height);
}

void dc1394cam::wait_for_trigger() const {
    std::cout << "DC1394CAM: Waiting for trigger signal... " << std::flush;
    for (;;) {
        if (check_buffer()) {
            std::cout << "done" << std::endl;
            break;
        }
    }
}

int dc1394cam::wait_for_image(int timeout) const {
    // Wait for data to arrive
    pollfd ufds[1];
    ufds[0].fd = m_fdcam;
    ufds[0].events = POLLIN;
    return poll(ufds, 1, timeout);
}

bool dc1394cam::check_buffer() const {
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET (m_fdcam, &fds);
    return select(m_fdcam + 1, &fds, NULL, NULL, NULL) > 0 && FD_ISSET(m_fdcam, &fds);
}
