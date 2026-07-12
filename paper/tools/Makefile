# Makefile — build the four HMS decision-signal variants for the ablation.
# Each object differs ONLY in -DHMS_SIGNAL; link with your real enforcer.o.
CC      ?= gcc
CFLAGS  ?= -Wall -Wextra -O2

VARIANTS = hms_footprint hms_rate hms_psi hms_hu

.PHONY: all objs test clean
all: objs

objs: hms_footprint.o hms_rate.o hms_psi.o hms_hu.o

hms_footprint.o: trigger_variants.c
	$(CC) $(CFLAGS) -DHMS_SIGNAL=HMS_FOOTPRINT -c $< -o $@
hms_rate.o: trigger_variants.c
	$(CC) $(CFLAGS) -DHMS_SIGNAL=HMS_RATE -c $< -o $@
hms_psi.o: trigger_variants.c
	$(CC) $(CFLAGS) -DHMS_SIGNAL=HMS_PSI -c $< -o $@
hms_hu.o: trigger_variants.c
	$(CC) $(CFLAGS) -DHMS_SIGNAL=HMS_HU -c $< -o $@

# Smoke test: build+run the H_u variant standalone (uses the built-in stub main).
test:
	$(CC) $(CFLAGS) -DHMS_STANDALONE_TEST -DHMS_SIGNAL=HMS_HU trigger_variants.c -o hms_hu_test
	./hms_hu_test

clean:
	rm -f *.o hms_hu_test
