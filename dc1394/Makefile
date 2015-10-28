CVCFLAGS = `pkg-config --cflags opencv`
CVLIBS = `pkg-config --libs opencv`
DC1394CFLAGS = `pkg-config --cflags libdc1394-2`
DC1394LIBS = `pkg-config --libs libdc1394-2`
SDLCFLAGS = `pkg-config --cflags sdl`
SDLLIBS = `pkg-config --libs sdl`
BOOSTFSLIBS = -lboost_filesystem -lboost_system
JPEGLIBS = -lturbojpeg
PNGLIBS = -lpng
OPT = -g0 -O3
CC = gcc
CXX = g++
LD = g++
CPPFLAGS = $(OPT) # -DINET
CXXFLAGS = 
OBJS_DC1394 = dc1394.o dc1394cam.o
OBJS_DC1394_SA = dc1394_sa.o dc1394cam_sa.o

all: dc1394 dc1394_sa

dc1394: $(OBJS_DC1394)
	$(LD) $(OBJS_DC1394) $(CVLIBS) $(DC1394LIBS) $(BOOSTFSLIBS) $(JPEGLIBS) $(PNGLIBS) $(SDLLIBS) -lpthread -o dc1394

dc1394.o: dc1394.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(CVCFLAGS) $(DC1394CFLAGS) $(SDLCFLAGS) -c dc1394.cpp

dc1394_sa: $(OBJS_DC1394_SA)
	$(LD) $(OBJS_DC1394_SA) $(CVLIBS) $(DC1394LIBS) $(BOOSTFSLIBS) $(JPEGLIBS) $(PNGLIBS) $(SDLLIBS) -lpthread -o dc1394_sa

dc1394_sa.o: dc1394.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -DSTANDALONE $(CVCFLAGS) $(DC1394CFLAGS) $(SDLCFLAGS) -c dc1394.cpp -o dc1394_sa.o

dc1394cam.o: dc1394cam.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(DC1394CFLAGS) -c dc1394cam.cpp

dc1394cam_sa.o: dc1394cam.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -DSTANDALONE $(DC1394CFLAGS) -c dc1394cam.cpp -o dc1394cam_sa.o

clean:
	rm -rf $(OBJS_DC1394) $(OBJS_DC1394_SA) dc1394 dc1394_sa
