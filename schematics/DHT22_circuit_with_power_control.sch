v 20130925 2
C 40000 40000 0 0 0 title-B.sym
C 46700 45500 1 0 0 2N2222-1.sym
{
T 47600 46200 5 10 0 0 0 0 1
device=2N2222
T 47600 46000 5 10 1 1 0 0 1
refdes=Q_PC
}
C 45600 45900 1 0 0 resistor-1.sym
{
T 45900 46300 5 10 0 0 0 0 1
device=10K
T 45800 46200 5 10 1 1 0 0 1
refdes=R_PC
T 45800 45700 5 10 1 1 0 0 1
value=10KΩ
}
C 47100 47600 1 90 0 resistor-1.sym
{
T 46700 47900 5 10 0 0 90 0 1
device=RESISTOR
T 46800 47700 5 10 1 1 90 0 1
refdes=R_DATA
T 47300 47800 5 10 1 1 90 0 1
value=4.7KΩ
}
N 46500 46000 46700 46000 4
C 47200 44600 1 0 0 gnd-1.sym
N 47300 45500 47300 44900 4
N 44500 46000 45600 46000 4
C 44900 47100 1 90 0 capacitor-1.sym
{
T 44200 47300 5 10 0 0 90 0 1
device=CAPACITOR
T 44600 47700 5 10 1 1 90 0 1
refdes=C_F
T 44000 47300 5 10 0 0 90 0 1
symversion=0.1
T 44900 47600 5 10 1 1 90 0 1
value=100nF
}
C 44500 46000 1 0 0 3.3V-plus-1.sym
C 44500 48500 1 0 0 5V-plus-1.sym
C 47700 46600 1 0 0 connector4-2.sym
{
T 49100 47500 5 10 1 1 0 6 1
refdes=DHT-22
T 48000 48650 5 10 0 0 0 0 1
device=CONNECTOR_4
T 48000 48850 5 10 0 0 0 0 1
footprint=SIP4N
T 47800 48300 5 10 1 1 0 0 1
pinlabel=+
T 47800 46800 5 10 1 1 0 0 1
pinlabel=-
T 47500 47900 5 10 1 1 0 0 1
pinlabel=DATA
}
N 44700 48000 44700 48500 4
N 44700 47000 47700 47000 4
N 47300 47000 47300 46500 4
N 44700 47000 44700 47100 4
C 43800 48400 1 0 0 input-1.sym
{
T 43800 48700 5 10 0 0 0 0 1
device=INPUT
T 43800 48200 5 10 1 1 0 0 1
netname=GPIO_5V
}
C 43700 45900 1 0 0 input-1.sym
{
T 43700 46200 5 10 0 0 0 0 1
device=INPUT
T 43600 45700 5 10 1 1 0 0 1
netname=GPIO-DATA_OUT-PC
}
C 46300 44800 1 0 0 input-1.sym
{
T 46300 45100 5 10 0 0 0 0 1
device=INPUT
T 46000 44600 5 10 1 1 0 0 1
netname=GPIO_GND
}
C 45500 47500 1 0 0 input-1.sym
{
T 45500 47800 5 10 0 0 0 0 1
device=INPUT
T 45200 47300 5 10 1 1 0 0 1
netname=GPIO_DATA_IN_S
}
N 47100 44900 47300 44900 4
N 44600 48500 47700 48500 4
N 47700 48500 47700 48200 4
N 46300 47600 47700 47600 4
N 47700 47600 47700 47800 4
C 46100 47600 1 0 0 3.3V-plus-1.sym