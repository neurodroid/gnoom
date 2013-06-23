OPT = -g0 -O3
CC = gcc
CXX = g++
LD = g++
CPPFLAGS = $(OPT)
CXXFLAGS = 
OBJS_READOUT =  readout.o
OBJS_STANDALONE =  readout_al.o

all: readout standalone

readout: $(OBJS_READOUT)
	$(LD) $(OBJS_READOUT) -lrt -o readout

readout.o: readout.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -c readout.cpp

standalone: $(OBJS_STANDALONE)
	$(LD) $(OBJS_STANDALONE) -lrt -o standalone

readout_al.o: readout.cpp
	$(CXX) $(CXXFLAGS) $(CPPFLAGS) -DSTANDALONE -c readout.cpp -o readout_al.o

clean:
	rm -rf $(OBJS_READOUT) $(OBJS_STANDALONE) readout standalone
