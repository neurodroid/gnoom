include $(top_srcdir)/Makefile.decl

AM_CPPFLAGS = -g -I$(top_srcdir)/src/ $(ARAVIS_CFLAGS)

AM_CFLAGS = -Wall

noinst_PROGRAMS = arv-camera-test

arv_camera_test_SOURCES = arvcameratest.cpp
arv_camera_test_LDADD = $(ARAVIS_LIBS) $(BOOST_FILESYSTEM_LIBS) $(BOOST_SYSTEM_LIBS)

