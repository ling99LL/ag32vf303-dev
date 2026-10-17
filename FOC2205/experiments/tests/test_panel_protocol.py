"""Telemetry and host authorization checks, independent of connected hardware."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from foc_protocol import PanelState, Status, Telemetry
from foc_panel import App


def frame(**changes):
    values = dict(proto=3,diag=1,fw='test',up=1000,hz=20000,stage=11,calst=0,calpk=0,calok=1,
                  ready=1,aligned=1,drvok=1,encok=1,mg=0,adcok=1,cal=1,
                  adce=0,brk=0,out=0,ang=0,crc=0,ia=0,ib=0,ic=0,mode=0,
                  mask=0,pct=10,drv='0x08',vq=0,iacc=0,err=0,vel=0,st=0,
                  cl=0,open=0,
                  vsp=0,vfb=0,verr=0,vkp=10,vki=50,vff=0,vfr=0,
                  hm=0,hact=0,hpos=0,hsub=0,htgt=0,hto=0,fault='')
    values.update(changes)
    return '#FOC,'+','.join(f'{key}={value}' for key,value in values.items())


class ProtocolTests(unittest.TestCase):
    def test_commands_wait_for_device_confirmation(self):
        app=App.__new__(App)
        sent=[]
        app.ser=SimpleNamespace(write=sent.append)
        app.model=PanelState()
        app._log=lambda text: None
        app.pct=SimpleNamespace(get=lambda:20)
        self.assertFalse(app._send('r'))
        self.assertTrue(app._send('s'))
        app.model.accept(Status.parse(frame(st=3,ready=0,aligned=0,drvok=0)),time.monotonic())
        self.assertFalse(app._send('z'))
        self.assertFalse(app._send('m'))
        app.model.accept(Status.parse(frame()),time.monotonic())
        app._toggle_manual()
        self.assertEqual(sent[-1],b'mw4')
        self.assertFalse(app.model.can_manual(time.monotonic()))
        self.assertFalse(app._send('x7'))
        app.model.accept(Status.parse(frame(st=1,mode=1,out=1,mask=0)),time.monotonic())
        app._toggle_phase(1)
        self.assertEqual(sent[-1],b'x2')
        self.assertEqual(app.model.status['mask'],0)
        self.assertFalse(app._send('r'))

    def test_calibration_is_explicit_and_cancellable(self):
        app=App.__new__(App)
        sent=[]
        app.ser=SimpleNamespace(write=sent.append)
        app.model=PanelState()
        app._log=lambda text: None
        app.model.accept(Status.parse(frame()),time.monotonic())
        self.assertTrue(app._send('a'))
        app.model.accept(Status.parse(frame(calst=4,calok=0,out=1)),time.monotonic())
        self.assertTrue(app.model.calibration_active(time.monotonic()))
        self.assertTrue(app._send('A'))
        self.assertEqual(sent[-1], b'A')

    def test_haptic_telemetry_and_authorization(self):
        app=App.__new__(App)
        sent=[]
        app.ser=SimpleNamespace(write=sent.append)
        app.model=PanelState()
        app._log=lambda text: None
        app.model.accept(Status.parse(frame(mode=3,hm=3,hact=1,hpos=2,hsub=20,st=1,out=1)),time.monotonic())
        self.assertTrue(app.model.haptic_active(time.monotonic()))
        self.assertTrue(app._send('m1\n'))
        self.assertTrue(app._send('dw 30\n'))
        app.model.accept(Status.parse(frame(mode=3,hm=1,hact=1,st=1,out=1)),time.monotonic()+0.1)
        tele=Telemetry.parse('$T,3,1,1234,-500,321,1500,0,0,1,1,20000')
        self.assertIsNotNone(tele)
        self.assertEqual(tele['hm'],1)
        self.assertAlmostEqual(tele['ang'],12.34)
        tele_raw=Telemetry.parse('$T,3,1,1234,-500,321,1500,0,0,1,1,20000,12345')
        self.assertIsNotNone(tele_raw)
        self.assertEqual(tele_raw['raw'],12345)
        tele_current=Telemetry.parse(
            '$T,3,1,1234,-500,321,1500,0,0,1,1,20000,12345,101,-202,303,1')
        self.assertIsNotNone(tele_current)
        self.assertEqual((tele_current['ia'], tele_current['ib'], tele_current['ic']),
                         (101, -202, 303))
        self.assertEqual(tele_current['adcok'], 1)
        self.assertIsNone(Telemetry.parse('$T,2,1,1234,-500,321,1500,0,0,1,1,20000'))
        self.assertIsNone(Telemetry.parse('$T,3,9,0,0,0,0,0,0,1,1,20000'))
        self.assertIsNone(Telemetry.parse('$T,3,1,1234,-500,321,1500,0,0,1,1,20000,16384'))
        self.assertIsNone(Telemetry.parse(
            '$T,3,1,1234,-500,321,1500,0,0,1,1,20000,12345,101,-202,303'))
        self.assertIsNone(Telemetry.parse(
            '$T,3,1,1234,-500,321,1500,0,0,1,1,20000,12345,101,-202,303,2'))

    def test_emergency_stop_is_always_sent(self):
        app=App.__new__(App)
        sent=[]
        app.ser=SimpleNamespace(write=sent.append)
        app.model=PanelState()
        app._log=lambda text: None
        app.command_pending_until=99.0
        app.spin_stop_at=88.0
        app.spin_status=SimpleNamespace(set=lambda text: None)
        app._emergency_stop()
        self.assertEqual(sent, [b'estop\n'])
        self.assertEqual(app.command_pending_until, 0.0)

    def test_missing_corrupt_old_frame_rejected(self):
        self.assertIsNone(Status.parse('#FOC,proto=3,ang=0'))
        self.assertIsNone(Status.parse(frame(proto=1)))
        self.assertIsNone(Status.parse(frame(diag=0)))
        self.assertIsNone(Status.parse(frame(ang='nan')))
        self.assertIsNone(Status.parse(frame(ang=16384)))
        self.assertIsNone(Status.parse(frame(ready=2)))
        self.assertIsNone(Status.parse(frame().replace(',cal=1','')))
        self.assertIsNone(Status.parse(frame(mode=3,hact=0)))
        self.assertIsNone(Status.parse(frame(hm=5)))

    def test_power_conditions(self):
        model=PanelState()
        self.assertFalse(model.can_drive(0))
        for field in ('ready','aligned','drvok','encok','adcok','cal'):
            model.accept(Status.parse(frame(**{field:0})),1)
            self.assertFalse(model.can_drive(1),field)
        model.accept(Status.parse(frame()),1)
        self.assertTrue(model.can_drive(2))
        self.assertFalse(model.can_drive(3.01))
        model.accept(Status.parse(frame(st=3,ready=0,aligned=0,drvok=0,fault='driver unavailable/config')),4)
        self.assertFalse(model.can_recover(4))
        self.assertFalse(model.can_drive(4))
        self.assertIn('VM',model.status.fault_text)
        model.accept(Status.parse(frame(st=3,ready=0,brk=1)),5)
        self.assertTrue(model.can_recover(5))
        model.accept(Status.parse(frame(st=1,mode=1,out=1)),6)
        self.assertTrue(model.can_manual(6))
        self.assertFalse(model.can_drive(6))
        self.assertFalse(model.can_manual(9))

    def test_closed_loop_velocity_status(self):
        status = Status.parse(frame(mode=2, st=1, out=1, pct=80,
                                    vsp=1638, vfb=1601, verr=37,
                                    vkp=10, vki=50, vff=0, vfr=0))
        self.assertIsNotNone(status)
        self.assertEqual(status['vsp'], 1638)
        self.assertEqual(status['vfb'], 1601)
        self.assertEqual(status['verr'], 37)
        self.assertEqual(status['vki'], 50)
        self.assertEqual(status['cl'], 0)
        self.assertEqual(status['open'], 0)

    def test_wrap_gap_invalid_and_reboot(self):
        model=PanelState()
        model.accept(Status.parse(frame(ang=16380)),1)
        model.accept(Status.parse(frame(ang=4,up=1100)),1.1)
        self.assertAlmostEqual(model.turns,8/16384)
        model.accept(Status.parse(frame(ang=3000,up=1200,encok=0)),1.2)
        model.accept(Status.parse(frame(ang=4000,up=1300)),1.3)
        self.assertAlmostEqual(model.turns,8/16384)
        model.accept(Status.parse(frame(ang=8000,up=5000)),5)
        self.assertAlmostEqual(model.turns,8/16384)
        self.assertTrue(model.accept(Status.parse(frame(ang=500,up=10)),5.1))
        self.assertEqual(model.turns,0)
        self.assertEqual(model.reboots,1)

    def test_uptime_wrap_is_not_reboot(self):
        model=PanelState()
        model.accept(Status.parse(frame(up=0xFFFFFFFE)),1)
        self.assertFalse(model.accept(Status.parse(frame(up=4)),1.1))


if __name__=='__main__':
    unittest.main()
