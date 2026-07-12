# HMS Kernel Module (Out-of-Tree, Research Scaffold)

> 파일/심볼 이름(`hmp_kmod`, `/dev/hmp_ctl` 등)은 구명칭(HMP)을 그대로 유지하지만,
> 시스템 명칭은 논문과 동일하게 **HMS (Heap Memory Safeguard)** 입니다.

이 모듈은 논문 속 HMS 개념을 **리눅스 커널 공간에서 실험**할 수 있도록 하는 최소 구현 예제입니다.
실제 memcg 훅, MTE 연동 등을 포함하지 않는 **연구용 스캐폴드**이며, sysfs를 통해 파라미터를 조정하고
간단한 메모리 지표를 관찰할 수 있습니다.

## 빌드

커널 헤더가 설치된 환경에서 다음을 수행합니다.

```bash
cd hmp/kernel
make -C /lib/modules/$(uname -r)/build M=$(pwd) modules
```

성공 시 `hmp_kmod.ko` 가 생성됩니다.

## 로드/언로드

```bash
sudo insmod hmp_kmod.ko
# 또는 파라미터 조정
# sudo insmod hmp_kmod.ko alpha_milli=350 theta1_milli=120 theta2_milli=180

# 상태 확인
ls /sys/kernel/hmp
cat /sys/kernel/hmp/stats

# 파라미터 조정
echo 300 | sudo tee /sys/kernel/hmp/alpha
echo 100 | sudo tee /sys/kernel/hmp/theta1
echo 200 | sudo tee /sys/kernel/hmp/theta2
echo 2048 | sudo tee /sys/kernel/hmp/rss_limit

# 언로드
sudo rmmod hmp_kmod
dmesg | tail -n 50
```

## 노출되는 sysfs 항목

- `/sys/kernel/hmp/alpha` : `alpha_milli` (예: 350 → 0.35)
- `/sys/kernel/hmp/theta1` : `theta1_milli` (예: 120 → 0.12)
- `/sys/kernel/hmp/theta2` : `theta2_milli` (예: 180 → 0.18)
- `/sys/kernel/hmp/rss_limit` : RSS 한도(MB) 정규화 기준
- `/sys/kernel/hmp/stats` : 불안정도(unstable), enforce 수준, Lr/Tgc/energy 등의 프록시 값

## 주의사항

- 이 모듈은 **실제 할당 경로를 제어하지 않습니다.** 실험 목적의 지표 산출과 파라미터 노출에 초점을 둡니다.
- memcg 또는 MTE/MTRR 등 하드웨어 기능과의 연동은 별도 인트리 패치가 필요합니다.
- 최신 커널(5.x/6.x)에서 동작하도록 일반 API만 사용했으나, 디스트로/버전에 따라 빌드 옵션이 필요할 수 있습니다.

## memcg / PSI 연동(스캐폴드)
- 커널 모듈이 **/proc/pressure/memory**(PSI)와 **cgroup v2 메모리 파일**을 읽어 지표를 반영합니다.
- 기본 cgroup 경로는 `/sys/fs/cgroup`이며, 서브 cgroup을 대상으로 할 경우 모듈 파라미터로 지정합니다:

```bash
sudo insmod hmp_kmod.ko cg_path=/sys/fs/cgroup/my.slice/my.scope
```

- `cat /sys/kernel/hmp/stats` 출력 예시:

```
unstable_milli=87
psi_avg10_milli=120
memcg_current_mb=512
memcg_max_mb=2048
enforce_pct=30
lr_ms=96
tgc_ms=20
energy_mw=96
```

> 주의: 커널 내부 PSI 심볼에 직접 의존하지 않고, procfs/cgroupfs 파일을 **kernel_read**로 읽는 방식이므로 커널 버전 호환성이 높습니다.

## /dev/hmp_ctl (char device)
- 모듈 로드시 `/dev/hmp_ctl`가 생성됩니다(udev 규칙에 따라 생성/퍼미션 부여).
- `read()` : JSON 스냅샷 1개를 반환 → 파라미터/지표를 한 번에 수집 가능
- `write()` : `key=value` 형태 한 줄로 파라미터 설정

### 예시
```bash
sudo insmod hmp_kmod.ko
# 스냅샷 조회
sudo cat /dev/hmp_ctl
# 파라미터 변경
echo 'alpha_milli=300' | sudo tee /dev/hmp_ctl
```

### 유저 공간 브리지 (Python)
```bash
python -m hmp.bridge --watch --interval 1.0
python -m hmp.bridge --set alpha_milli 350 --set theta1_milli 120
```
