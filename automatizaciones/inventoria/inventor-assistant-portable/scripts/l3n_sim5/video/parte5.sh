#!/bin/bash
# uso: parte5.sh desde hasta  -> ~/work/parts5/p_desde.mp4 (30 fps, crf 19 medium)
a=$1; b=$2
lst=~/work/parts5/l_$a.txt
: > $lst
for i in $(seq $a $b); do f=$(printf "%s/work/rot5/c%05d.jpg" $HOME $i); [ -f $f ] || { echo "falta $f"; exit 1; }; echo "file '$f'" >> $lst; echo "duration 0.033333" >> $lst; done
ffmpeg -y -loglevel error -f concat -safe 0 -i $lst -vf "fps=30,format=yuv420p" -c:v libx264 -crf 19 -preset medium -movflags +faststart ~/work/parts5/p_$(printf %05d $a).mp4 && echo ok $a $b
