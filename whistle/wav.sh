#!/bin/sh
PIPELINE="freqx,-10000:kbfir,41,0,1000,100:freqx,1000:amplify,100"
SAMP_RATE=`soxi -r $1`
SOX_FORMAT="-c 2 -b 32 -r $SAMP_RATE -t raw -e floating-point"
sox $1 $SOX_FORMAT - | ./whistle -r $SAMP_RATE -p $PIPELINE | sox $SOX_FORMAT - $2
