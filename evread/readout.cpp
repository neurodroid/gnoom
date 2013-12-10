// This program is free software; you can redistribute it and/or
// modify it under the terms of the GNU General Public License
// as published by the Free Software Foundation; either version 2
// of the License, or (at your option) any later version.

// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

/*! \file readout.cpp
 *  \author Christoph Schmidt-Hieber
 *  \date 2011-10-29
 *  \brief Reads out mice using the input subsystem
 */

#include <vector>
#include <cstdio>
#include <cstddef>
#include <iostream>
#include <ctime>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/types.h>
#include <sstream>
#include <algorithm>
#include <fcntl.h>
#include <unistd.h>
#include <termios.h>
#include <sys/ioctl.h>
#include <linux/input.h>

static const double BILLION = 1000000000L;
static const double TIMEOUT = 4.0;
static const int BUFSIZE = 4096;
static const int MOUSE1_EVNO = 3;
static const int MOUSE2_EVNO = 5;

double tdiff(timespec time1, timespec time0) {
    return ( time1.tv_sec - time0.tv_sec )
        + ( time1.tv_nsec - time0.tv_nsec ) / BILLION;
}

double t2d(timespec time1) {
    return time1.tv_sec + time1.tv_nsec / BILLION;
}

int main (int argc, char **argv)
{
    // parse arguments:
    int index = MOUSE1_EVNO;
    int socketno = 0;
    char* ntry = (char*)"";
    if (argc > 1) {
        // std::cout << argv[1][0] << std::endl;
        index = atoi(argv[1]);
        if (argc > 2) {
            socketno = atoi(argv[2]);
        }
	if (argc > 3) {
            ntry = argv[3];
	}
    }

#ifndef STANDALONE
    int s;
    if ((s = socket(AF_UNIX, SOCK_STREAM, 0)) < 0) {
        perror("USBREAD: server: socket");
        return -1;
    }

    /*
     * Create the address we will be connecting to.
     */
    sockaddr_un saun;

    std::ostringstream tmpfn;
    tmpfn << "mouse" << socketno << "socket" << ntry;
    std::cout << "USBREAD: socket name " << tmpfn.str() << std::endl;

    int nameLen = strlen(tmpfn.str().c_str());
    if (nameLen >= (int) sizeof(saun.sun_path) -1)  /* too long? */
        return -1;

    saun.sun_family = AF_UNIX;
    saun.sun_path[0] = '\0';  /* abstract namespace */
    strcpy(saun.sun_path+1, tmpfn.str().c_str());

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
    int len = 1 + nameLen + offsetof(struct sockaddr_un, sun_path);
    if (connect(s, (sockaddr*)&saun, len) < 0) {
        perror("USBREAD: client: connect");
        return -1;
    }

    bool connected = false;
    std::vector<char> data(BUFSIZE);
    int nrec = recv(s, &data[0], data.size(), 0);
    std::string datastr(data.begin(), data.end());
    if ((nrec<5) ||(datastr.substr(0,5) != "start")) {
        std::cerr << "USBREAD: Didn't receive start; exiting now" << std::endl;
	close(s);
        return -1;
    }
    connected = true;
    
    std::string ready = "ready";
    while (send(s, ready.c_str(), ready.size(), 0) < 0) {
        perror("USBREAD: client: send");
    }

    int flags;
    if (-1 == (flags = fcntl(s, F_GETFL, 0)))
        flags = 0;

    if (fcntl(s, F_SETFL, flags | O_NONBLOCK)==-1) {
        perror("USBREAD: client: unblock");
    }
#endif
    std::ostringstream devname;
    devname << "/dev/input/event" << index;
    std::cout << "USBREAD: opening device " << devname.str() << "... " << std::flush;
    int fd_dev = open(devname.str().c_str(), O_RDONLY);
    if (fd_dev == -1) {
        perror("cannot open output file\n");
        exit(1);
    }
    std::cout << "success" << std::endl;
    
    std::vector<int> readout(2);
#ifndef STANDALONE
    std::vector<double> buffer;
#endif
    struct timespec time0, time1, t_disconnect, t_sent, t_loop, t_poll;
    if( clock_gettime( CLOCK_REALTIME, &time0) == -1 ) {
        fprintf(stderr, "USBREAD: clock gettime");
#ifndef STANDALONE
	close(s);
#endif
        return -1;
    }

    t_sent = time0;
    t_disconnect = time0;
    t_poll = time0;
#ifdef STANDALONE
    bool print = true;
    double sumx = 0;
    double sumy = 0;

#else
    bool print = false;
#endif

    /* empty buffer */
    int iBytesRead = 0;
    std::vector<input_event> ev(64);

    struct timeval tv;
    tv.tv_sec  = 0;
    tv.tv_usec = 0;

    int  iSelRet = 0;
    fd_set fds;

    bool has_data = false;
    
    while (true) {
        clock_gettime( CLOCK_REALTIME, &t_loop);

#ifndef STANDALONE
        std::vector<char> data(BUFSIZE);
        int nrec = recv(s, &data[0], data.size(), 0);
        std::string datastr(data.begin(), data.end());
	// std::cout << datastr << std::endl;
        if (datastr.find("1")==std::string::npos) {
            if (connected) {
                t_disconnect = t_loop;
                connected = false;
            } else {
                if (tdiff(t_loop, t_disconnect) > TIMEOUT) {
                    std::cout << "USBREAD: timeout, exiting now." << std::endl;
		    close(s);
                    return 0;
                }
            }
        } else {
            connected = true;
        }
	/* Explicit termination */
        if (datastr.find("quit")!=std::string::npos) {
            std::cout << "USBREAD: Game over signal." << std::endl;
            std::string sclose = "close";
            while (send(s, sclose.c_str(), sclose.size(), 0) < 0) {
                perror("USBREAD: client: send");
            }
            close(s);
            return 0;
        }
#endif

        FD_ZERO(&fds);
        FD_SET (fd_dev, &fds);

        iSelRet = select(fd_dev + 1, &fds, NULL, NULL, &tv);
        tv.tv_sec  = 0;
        tv.tv_usec = 50000;

        has_data = false;

        clock_gettime( CLOCK_REALTIME, &time1);
        double accum = tdiff(time1, time0);
        clock_gettime( CLOCK_REALTIME, &time0);
        double dtime1 = t2d(time1);

        if(iSelRet > 0 && FD_ISSET(fd_dev, &fds) == true)
        {
            
            iBytesRead = read(fd_dev, &ev[0], sizeof(input_event) * 64);

            for (int i = 0; i < int(iBytesRead / sizeof(input_event)); ++i) {
                if(ev[i].type == EV_REL) {
                    switch(ev[i].code) {
                     case REL_X:
                         readout[0] = ev[i].value;
                         has_data = true;
                         break;
                     case REL_Y:
                         readout[1] = ev[i].value;
                         has_data = true;
                         break;
                     default:
                         break;
                    }
                }
            }
            if (has_data) {
#ifndef STANDALONE
                buffer.push_back(dtime1);
                buffer.push_back(accum);
                buffer.push_back(double(readout[0]));
                buffer.push_back(double(readout[1]));
#else
                sumx += readout[0];
                sumy += readout[1];
                std::cout << tdiff(time1, t_poll) << "\t" <<  readout[0] << "\t" << readout[1] << "\t";
                std::cout << sumx << "\t";
                std::cout << sumy << std::endl << std::flush;
                clock_gettime( CLOCK_REALTIME, &t_poll);
#endif
            }
        }
#ifndef STANDALONE
        if (!has_data) {
            buffer.push_back(dtime1);
            buffer.push_back(accum);
            buffer.push_back(0.0);
            buffer.push_back(0.0);
        }
        if (tdiff(time1, t_sent) > 0.01) {
            t_sent = time1;
            if (send(s, &buffer[0], sizeof(double)*buffer.size(), 0) < 0) {
                if (has_data) {
                    perror("USBREAD: terminating, send failed");
		    close(s);
                    return 0;
                } else {
                    // perror("USBREAD: send failed; will try again later");
                }
            } else {
                buffer.clear();
            }
        }
#endif

    }
#ifndef STANDALONE
    close(s);
#endif
    return 0;
}
