CVCFLAGS = `pkg-config --cflags opencv`
CVLIBS = `pkg-config --libs opencv`
OPT = -g0 -O3
CC = gcc
CXX = g++
LD = g++
CPPFLAGS = $(OPT)
CXXFLAGS = 
OBJS_WEBCAM = webcam.o
OBJS_WEBCAM_SA = webcam_sa.o

all: webcam webcam_sa

webcam: $(OBJS_WEBCAM)
	$(LD) $(OBJS_WEBCAM) $(CVLIBS) -o webcam

webcam.o: webcam.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) $(CVCFLAGS) -c webcam.cpp

webcam_sa: $(OBJS_WEBCAM_SA)
	$(LD) $(OBJS_WEBCAM_SA) $(CVLIBS) -o webcam_sa

webcam_sa.o: webcam.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -DSTANDALONE $(CVCFLAGS) -c webcam.cpp -o webcam_sa.o

clean:
	rm -rf $(OBJS_WEBCAM) $(OBJS_WEBCAM_SA) webcam webcam_sa
