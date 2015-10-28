#include <dc1394/dc1394.h>
#include <sys/types.h>

class dc1394cam {
  public:
    dc1394cam();
    dc1394cam(dc1394_t *d, uint64_t guid);
   ~dc1394cam();

    int init(dc1394_t *d, uint64_t guid);
    void free();
    dc1394error_t start_transmission();
    dc1394error_t start_capture();
    dc1394camera_t* cam();
    void get_image_size(uint32_t* width, uint32_t* height) const;
    bool check_buffer() const;
    void wait_for_trigger() const;
    int wait_for_image(int timeout=2000) const;
    uint32_t get_mingain() const {return m_mingain;}
    uint32_t get_maxgain() const {return m_maxgain;}

  private:

    dc1394camera_t *m_cam;
    dc1394video_mode_t m_video_mode;
    int m_fdcam;
    uint32_t m_mingain, m_maxgain;
    bool is_transmitting, is_capturing;
};
