ifneq ($(V),1)
		Q := @
endif

INCDIR		= -I include/
CCFLAGS		= -g -O2 $(INCDIR)
CXXFLAGS	= $(CCFLAGS)
LDFLAGS		= -export-dynamic
LIBS		= -ljack -ldl -lm
CC			= gcc $(CCFLAGS)
LD			= gcc $(LDFLAGS)

BIN			= whistle
OBJS		= whistle.o

all: $(BIN)

clean:
	$(Q) rm -f *.o $(BINS) $(OBJS)
	@printf "  CLEAN\n";

.c.o:
	@printf "  CC  $(subst $(shell pwd)/,,$(@))\n";
	$(Q) $(CC) -c -o$@ $<

$(BIN): $(OBJS)
	@printf "  LD  $(subst $(shell pwd)/,,$(@))\n";
	$(Q) $(LD) -o$@ $(OBJS) $(LIBS)
