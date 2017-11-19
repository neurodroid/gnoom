OPT = -g0 -O3
CC = gcc
CXX = g++
LD = g++
CPPFLAGS = $(OPT)
CXXFLAGS = 
OBJS_READOUT =  readout.o
OBJS_READOUT_ZMQ =  readout_zmq.o
OBJS_STANDALONE =  readout_al.o

all: readout readout_zmq standalone

readout: $(OBJS_READOUT)
	$(LD) $(OBJS_READOUT) -lrt -o readout

readout.o: readout.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c readout.cpp

readout_zmq: $(OBJS_READOUT_ZMQ)
	$(LD) -lzmq $(OBJS_READOUT_ZMQ) -lrt -o readout_zmq

readout_zmq.o: readout.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -DUSE_ZMQ -c readout.cpp -o readout_zmq.o

standalone: $(OBJS_STANDALONE)
	$(LD) $(OBJS_STANDALONE) -lrt -o standalone

readout_al.o: readout.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -DSTANDALONE -c readout.cpp -o readout_al.o

clean:
	rm -rf $(OBJS_READOUT) $(OBJS_READOUT_ZMQ) $(OBJS_STANDALONE) readout readout_zmq standalone
