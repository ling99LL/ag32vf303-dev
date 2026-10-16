# Verify the debugger halt really freezes the core: the PC must not move while
# the GPTIMER counter keeps counting (the break filter is clocked by the bus).
init
halt
echo [reg pc]
mem2array c1 32 0x40020024 1
echo "CNT1=$c1(0)"
sleep 1500
echo [reg pc]
mem2array c2 32 0x40020024 1
echo "CNT2=$c2(0)"
sleep 1500
echo [reg pc]
mem2array c3 32 0x40020024 1
echo "CNT3=$c3(0)"
echo [reg pc]
resume
shutdown
