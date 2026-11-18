"""자원·전력 측정 도구 (Windows).

1초에 한 번 CPU 와 메모리를 재고, 노트북이 Windows Energy Meter Interface(EMI)를 제공하면
실제 전력(W)을 읽는다. 결과는 power_experiment/ 아래 CSV 로 남긴다.
CPU 사용률을 W 로 바꾸지 않는다. EMI 를 읽을 수 없으면 전력은 "측정 불가"로 둔다.

사용법 (프로젝트 폴더에서):
    python tools/power_monitor.py check                      # 직접 전력 측정이 되는지 확인
    python tools/power_monitor.py run idle --seconds 60      # 조건 하나를 60초 측정
조건: idle(앱을 켜지 않음) / detection(1페이지 감시, 재인증 없음) /
      reauth(재인증 2번 성공) / edge(reauth 와 같고 Supabase 전송 켜짐)
"""

import argparse
import csv
import ctypes
import platform
import sys
import time
import uuid
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

import psutil

PROJECT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT / "power_experiment"
SUMMARY_PATH = OUT_DIR / "summary.csv"
NOT_MEASURED = "측정 불가"

CONDITIONS = {
    "idle": "앱을 켜지 않은 상태. 이 측정 동안 Streamlit 앱을 끄고 아무것도 하지 마세요.",
    "detection": "앱을 켜고 1페이지 감시 중. 측정 동안 tie5roan1 을 평소처럼 계속 입력하세요(재인증 없이).",
    "reauth": "앱을 켜고 1페이지 감시 중. 측정 동안 재인증을 2번 일으키고 맞는 PIN 으로 2번 성공하세요.",
    "edge": "reauth 와 똑같이 하되, 3페이지 '통신 단절 (모의)' 스위치를 끈 상태(Supabase 전송 켜짐)로 하세요.",
}
SUMMARY_COLUMNS = [
    "condition", "started_at", "seconds", "samples", "app_processes",
    "system_cpu_mean", "app_cpu_mean", "app_rss_mb_mean",
    "power_w_mean", "power_source", "power_channels",
    "cpu_model", "logical_cpus", "power_supply",
]


# ---------- 대상 프로세스: 이 프로젝트의 Streamlit 앱 ----------

def is_app_process(process):
    """이 프로젝트의 `streamlit run app.py` 를 돌리는 파이썬 프로세스인지."""
    try:
        name = process.name().lower()
        cmdline = [part.lower() for part in process.cmdline()]
        cwd = Path(process.cwd()).resolve()
    except (psutil.Error, OSError):
        return False
    if not name.startswith("python"):
        return False
    joined = " ".join(cmdline)
    if "streamlit" not in joined or " run" not in f" {joined}" or "app.py" not in joined:
        return False
    # 다른 폴더의 Streamlit 앱은 빼고, 이 프로젝트에서 실행한 것만
    app_args = [part for part in cmdline if part.endswith("app.py")]
    for arg in app_args:
        path = Path(arg) if Path(arg).is_absolute() else cwd / arg
        if path.resolve() == (PROJECT / "app.py").resolve():
            return True
    return False


def find_app_processes():
    return [p for p in psutil.process_iter() if is_app_process(p)]


# ---------- Windows Energy Meter Interface (EMI) ----------
# 문서로 확인한 것: 장치 인터페이스 GUID, AbsoluteEnergy(피코와트시), AbsoluteTime(100ns 단위).
#   https://learn.microsoft.com/windows-hardware/drivers/powermeter/energy-meter-interface
# 문서에 숫자가 없던 것: 아래 IOCTL 숫자와 버전 상수, EMI_NAME_MAX. 이 PC 에 Windows SDK(emi.h)도 없어서
#   emi.h 의 정의로 알려진 값을 적었다. 2026-11-18 이 노트북(i7-1065G7)에서 이 값들로 읽었을 때
#   버전 2, 제조사 "Microsoft", 모델 "PPM", 채널 RAPL_Package0_PKG/DRAM/PP0/PP1 이 정상적으로 나왔다.
#   다른 PC 에서 값이 이상하게 읽히면 "측정 불가"로 둔다.
# 이 노트북의 채널은 CPU 의 RAPL 센서다. PKG 는 CPU 패키지 전력이고, 노트북 전체 전력이 아니다.

GUID_DEVICE_ENERGY_METER = "{45BD8344-7ED6-49cf-A440-C276C933B053}"


def ctl_code(device_type, function, method, access):
    return (device_type << 16) | (access << 14) | (function << 2) | method


_FILE_DEVICE_UNKNOWN, _METHOD_BUFFERED, _FILE_READ_ACCESS = 0x22, 0, 1
IOCTL_EMI_GET_VERSION = ctl_code(_FILE_DEVICE_UNKNOWN, 0, _METHOD_BUFFERED, _FILE_READ_ACCESS)        # 미확인
IOCTL_EMI_GET_METADATA_SIZE = ctl_code(_FILE_DEVICE_UNKNOWN, 1, _METHOD_BUFFERED, _FILE_READ_ACCESS)  # 미확인
IOCTL_EMI_GET_METADATA = ctl_code(_FILE_DEVICE_UNKNOWN, 2, _METHOD_BUFFERED, _FILE_READ_ACCESS)       # 미확인
IOCTL_EMI_GET_MEASUREMENT = ctl_code(_FILE_DEVICE_UNKNOWN, 3, _METHOD_BUFFERED, _FILE_READ_ACCESS)    # 미확인
EMI_VERSION_V1, EMI_VERSION_V2 = 1, 2   # 미확인
EMI_NAME_MAX = 16                       # 미확인
UNIT_PICOWATT_HOURS = 0                 # EMI_MEASUREMENT_UNIT 의 첫 값 (미확인)


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.c_size_t)]


def make_guid(text):
    return GUID.from_buffer_copy(uuid.UUID(text).bytes_le)


def device_interface_paths(guid_text):
    """그 GUID 로 등록된, 지금 연결된 장치 인터페이스의 경로 목록."""
    if platform.system() != "Windows":
        return []
    setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
    setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    setupapi.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
    setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
    setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]

    DIGCF_PRESENT, DIGCF_DEVICEINTERFACE = 0x2, 0x10
    ERROR_NO_MORE_ITEMS = 259
    guid = make_guid(guid_text)
    handle = setupapi.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if handle in (None, wintypes.HANDLE(-1).value):
        raise OSError(ctypes.get_last_error(), "SetupDiGetClassDevsW 실패")
    paths = []
    try:
        index = 0
        while True:
            data = SP_DEVICE_INTERFACE_DATA()
            data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not setupapi.SetupDiEnumDeviceInterfaces(handle, None, ctypes.byref(guid), index, ctypes.byref(data)):
                error = ctypes.get_last_error()
                if error == ERROR_NO_MORE_ITEMS:
                    break
                raise OSError(error, "SetupDiEnumDeviceInterfaces 실패")
            required = wintypes.DWORD()
            setupapi.SetupDiGetDeviceInterfaceDetailW(handle, ctypes.byref(data), None, 0, ctypes.byref(required), None)
            buffer = ctypes.create_string_buffer(required.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W.cbSize: 64비트 8, 32비트 6
            ctypes.c_uint32.from_buffer(buffer).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if setupapi.SetupDiGetDeviceInterfaceDetailW(handle, ctypes.byref(data), buffer, required, None, None):
                paths.append(ctypes.wstring_at(ctypes.addressof(buffer) + 4))
            index += 1
    finally:
        setupapi.SetupDiDestroyDeviceInfoList(handle)
    return paths


class EmiMeter:
    """EMI 장치 하나. read() 는 채널마다 (AbsoluteEnergy pWh, AbsoluteTime 100ns) 를 돌려준다."""

    def __init__(self, path):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                         wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                             ctypes.c_void_p]
        self.kernel32 = kernel32
        GENERIC_READ, FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING = 0x80000000, 1, 2, 3
        self.handle = kernel32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                           None, OPEN_EXISTING, 0, None)
        if self.handle == wintypes.HANDLE(-1).value:
            raise OSError(ctypes.get_last_error(), "EMI 장치를 열 수 없음")
        self.version = int.from_bytes(self.ioctl(IOCTL_EMI_GET_VERSION, 2)[:2], "little")
        if self.version not in (EMI_VERSION_V1, EMI_VERSION_V2):
            raise ValueError(f"알 수 없는 EMI 버전 {self.version}")
        size = int.from_bytes(self.ioctl(IOCTL_EMI_GET_METADATA_SIZE, 4)[:4], "little")
        self.oem, self.model, self.channels = self.parse_metadata(self.ioctl(IOCTL_EMI_GET_METADATA, size))

    def ioctl(self, code, out_size):
        out = ctypes.create_string_buffer(out_size)
        returned = wintypes.DWORD()
        if not self.kernel32.DeviceIoControl(self.handle, code, None, 0, out, out_size, ctypes.byref(returned), None):
            raise OSError(ctypes.get_last_error(), f"DeviceIoControl 0x{code:X} 실패")
        return out.raw

    def parse_metadata(self, raw):
        """메타데이터에서 제조사, 모델, [(채널 이름, 단위)] 를 읽는다."""
        def wstr(data):
            return data.decode("utf-16-le", errors="replace").split("\x00")[0]

        name_bytes = EMI_NAME_MAX * 2
        if self.version == EMI_VERSION_V1:
            unit = int.from_bytes(raw[0:4], "little")
            oem = wstr(raw[4:4 + name_bytes])
            model = wstr(raw[4 + name_bytes:4 + 2 * name_bytes])
            offset = 4 + 2 * name_bytes + 2
            name_size = int.from_bytes(raw[offset:offset + 2], "little")
            name = wstr(raw[offset + 2:offset + 2 + name_size])
            return oem, model, [(name, unit)]
        oem = wstr(raw[0:name_bytes])
        model = wstr(raw[name_bytes:2 * name_bytes])
        count = int.from_bytes(raw[2 * name_bytes + 2:2 * name_bytes + 4], "little")
        offset = 2 * name_bytes + 4
        channels = []
        for _ in range(count):
            unit = int.from_bytes(raw[offset:offset + 4], "little")
            name_size = int.from_bytes(raw[offset + 4:offset + 6], "little")
            channels.append((wstr(raw[offset + 6:offset + 6 + name_size]), unit))
            offset += 6 + name_size
        return oem, model, channels

    def read(self):
        raw = self.ioctl(IOCTL_EMI_GET_MEASUREMENT, 16 * len(self.channels))
        readings = []
        for i in range(len(self.channels)):
            energy = int.from_bytes(raw[16 * i:16 * i + 8], "little")
            ticks = int.from_bytes(raw[16 * i + 8:16 * i + 16], "little")
            readings.append((energy, ticks))
        return readings


def average_watts(earlier, later):
    """두 읽기 사이의 평균 전력(W). 에너지 pWh, 시간 100ns 단위."""
    energy_pwh = later[0] - earlier[0]
    ticks = later[1] - earlier[1]
    if ticks <= 0 or energy_pwh < 0:
        return None
    return energy_pwh * 1e-12 * 3600 / (ticks * 1e-7)


def open_meter():
    """쓸 수 있는 EMI 장치를 연다. (meter, 이유) 를 돌려주고, 못 쓰면 meter 는 None."""
    try:
        paths = device_interface_paths(GUID_DEVICE_ENERGY_METER)
    except OSError as error:
        return None, f"EMI 장치를 찾는 중 오류: {error}"
    if not paths:
        return None, "이 노트북에는 EMI 에너지 미터 장치가 없습니다"
    for path in paths:
        try:
            meter = EmiMeter(path)
        except (OSError, ValueError) as error:
            last_error = f"EMI 장치를 읽을 수 없음: {error}"
            continue
        if all(unit == UNIT_PICOWATT_HOURS for _, unit in meter.channels):
            return meter, "EMI 장치를 읽을 수 있습니다"
        last_error = "EMI 단위가 피코와트시가 아님"
    return None, last_error


# ---------- 측정 조건 ----------

def cpu_model():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    except Exception:
        return platform.processor() or "알 수 없음"


def power_supply():
    battery = psutil.sensors_battery()
    if battery is None:
        return "알 수 없음"
    return f"{'전원 어댑터' if battery.power_plugged else '배터리'} ({battery.percent:.0f}%)"


# ---------- 명령 ----------

def command_check():
    print(f"CPU: {cpu_model()} / 논리 CPU {psutil.cpu_count()}개 / RAM {psutil.virtual_memory().total / 1024**3:.1f} GB")
    print(f"전원: {power_supply()}")
    apps = find_app_processes()
    print(f"이 프로젝트의 Streamlit 앱 프로세스: {len(apps)}개" + (f" (PID {', '.join(str(p.pid) for p in apps)})" if apps else ""))
    meter, reason = open_meter()
    if meter is None:
        print(f"직접 전력 측정: 불가 - {reason}. 전력은 '{NOT_MEASURED}'로 기록됩니다.")
        return 1
    names = ", ".join(name for name, _ in meter.channels)
    print(f"직접 전력 측정: 가능 - Windows EMI v{meter.version}, {meter.oem} {meter.model}, 채널: {names}")
    first = meter.read()
    time.sleep(1)
    second = meter.read()
    for (name, _), a, b in zip(meter.channels, first, second):
        watts = average_watts(a, b)
        print(f"  {name}: {'-' if watts is None else f'{watts:.2f} W'} (1초 평균)")
    return 0


def command_run(condition, seconds):
    print(f"[{condition}] {CONDITIONS[condition]}")
    apps = find_app_processes()
    if condition == "idle" and apps:
        print(f"앱이 켜져 있습니다(PID {', '.join(str(p.pid) for p in apps)}). idle 은 앱을 끄고 재세요.")
        return 2
    if condition != "idle" and not apps:
        print("이 프로젝트의 Streamlit 앱을 찾지 못했습니다. 먼저 `streamlit run app.py` 로 켜세요.")
        return 2

    meter, reason = open_meter()
    channel_names = [] if meter is None else [name for name, _ in meter.channels]
    # 요약의 대표 전력은 첫 채널이다 (이 노트북에서는 RAPL_Package0_PKG = CPU 패키지 전력)
    source = NOT_MEASURED if meter is None else f"Windows EMI {meter.oem} {meter.model} / {channel_names[0]}"
    print(f"전력: {source}" + ("" if meter else f" - {reason}"))

    OUT_DIR.mkdir(exist_ok=True)
    started = datetime.now().astimezone()
    raw_path = OUT_DIR / f"raw_{condition}_{started:%Y%m%d_%H%M%S}.csv"
    columns = ["time", "elapsed_s", "system_cpu", "app_cpu", "app_rss_mb"] + [f"power_w[{n}]" for n in channel_names]

    psutil.cpu_percent(None)
    for p in apps:
        p.cpu_percent(None)
    previous = meter.read() if meter else None
    rows = []
    start = time.monotonic()
    print(f"{seconds}초 측정을 시작합니다. 끝나면 요약을 저장합니다.")
    with raw_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for i in range(1, seconds + 1):
            time.sleep(max(0.0, start + i - time.monotonic()))
            row = {"time": datetime.now().astimezone().isoformat(timespec="seconds"),
                   "elapsed_s": i, "system_cpu": psutil.cpu_percent(None)}
            app_cpu, app_rss = 0.0, 0
            for p in apps:
                try:
                    app_cpu += p.cpu_percent(None)
                    app_rss += p.memory_info().rss
                except psutil.Error:
                    pass
            row["app_cpu"] = app_cpu if apps else ""
            row["app_rss_mb"] = round(app_rss / 1024**2, 1) if apps else ""
            if meter:
                current = meter.read()
                for name, a, b in zip(channel_names, previous, current):
                    watts = average_watts(a, b)
                    row[f"power_w[{name}]"] = "" if watts is None else round(watts, 3)
                previous = current
            writer.writerow(row)
            rows.append(row)
            if i % 10 == 0:
                print(f"  {i}/{seconds}초")

    summary = summarize(condition, started, seconds, rows, apps, source, channel_names)
    append_summary(summary)
    print(f"원자료: {raw_path.relative_to(PROJECT)}")
    print(f"요약: {SUMMARY_PATH.relative_to(PROJECT)}")
    for key in ["system_cpu_mean", "app_cpu_mean", "app_rss_mb_mean", "power_w_mean", "power_source"]:
        print(f"  {key}: {summary[key]}")
    return 0


def mean(values):
    values = [float(v) for v in values if v not in ("", None)]
    return round(sum(values) / len(values), 3) if values else ""


def summarize(condition, started, seconds, rows, apps, source, channel_names):
    channels = []
    for name in channel_names:
        channels.append(f"{name}={mean(r.get(f'power_w[{name}]') for r in rows)}")
    first_channel = mean(r.get(f"power_w[{channel_names[0]}]") for r in rows) if channel_names else ""
    return {
        "condition": condition,
        "started_at": started.isoformat(timespec="seconds"),
        "seconds": seconds,
        "samples": len(rows),
        "app_processes": len(apps),
        "system_cpu_mean": mean(r["system_cpu"] for r in rows),
        "app_cpu_mean": mean(r["app_cpu"] for r in rows),
        "app_rss_mb_mean": mean(r["app_rss_mb"] for r in rows),
        "power_w_mean": first_channel,
        "power_source": source if first_channel != "" else NOT_MEASURED,
        "power_channels": "; ".join(channels),
        "cpu_model": cpu_model(),
        "logical_cpus": psutil.cpu_count(),
        "power_supply": power_supply(),
    }


def append_summary(summary):
    is_new = not SUMMARY_PATH.exists()
    with SUMMARY_PATH.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(summary)


def main(argv=None):
    parser = argparse.ArgumentParser(description="자원·전력 측정 도구")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="직접 전력 측정이 되는지 확인")
    run = sub.add_parser("run", help="조건 하나를 측정")
    run.add_argument("condition", choices=list(CONDITIONS))
    run.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args(argv)
    if args.command == "check":
        return command_check()
    return command_run(args.condition, args.seconds)


if __name__ == "__main__":
    sys.exit(main())
