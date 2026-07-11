# WP-INFRA-IO-001 — Incident Analysis (Read IOPS)

**Status:** Investigation only — no production configuration changes applied.  
**Host:** `40057` (KVM / RDO OpenStack, `QEMU HARDDISK` 80G, `ROTA=1`)  
**Timezone of all timestamps below:** **UTC** (system clock / sysstat / journal).  
**Date of primary incident window:** 2026-07-11  

---

## 1. Executive summary

PS.kz’s finding of **disk Read IOPS saturation** is confirmed by local `sar -d` and `atop` archives for **14:00–14:10 UTC**.

The afternoon degradation coincides with:

1. **Repeated Next.js production builds / frontend restarts** (new `BUILD_ID` at 13:26, 13:50, 14:00, 14:07).
2. **Active Cursor Server remote session** (`fileWatcher`, `extensionHost`, indexing / grep).
3. **Mass Cursor file-watcher teardown** at **13:47** (“watched path got deleted”) — consistent with `.next` (or similar) being wiped mid-build while Cursor was watching the tree.
4. **Severe page-cache reclaim / scanning** during the peak (`atop` `PAG`), with memory commit ≥100% — a plausible amplifier of **Read** IOPS (re-read of recently written/evicted pages).

**No single process was proven as the sole physical reader** (atop process disk counters use stdio accounting; 10-minute samples also miss short-lived `npm`/`next` PIDs). Attribution is therefore **multi-factor with high confidence on timing correlation**, not a single PID smoking gun.

PostgreSQL/Docker were running but **do not show as the dominant spike driver** in available evidence (low Docker network rates during the peak; no DB-specific read storm proven).

---

## 2. Proven facts vs hypotheses

### Proven facts (high confidence)

| Fact | Evidence | Confidence |
|------|----------|------------|
| Disk Read IOPS saturated ~14:00–14:10 UTC | `sar -d -f /var/log/sysstat/sa11`: sda `r/s≈665` / `rkB/s≈61MB/s` / `await≈177ms` / `aqu-sz≈118` at 14:00; `r/s≈837` / `rkB/s≈127MB/s` / `await≈189ms` / `aqu-sz≈158` at 14:10 | **High** |
| Spike is read-dominated (writes comparatively small) | Same `sar` rows: `wkB/s` ≈ 3.0 / 1.3 MB/s vs reads 61 / 127 MB/s | **High** |
| CPU spent heavily in iowait during spike | `sar -u`: `%iowait` 44.15% (14:00), 28.28% (14:10); loadavg-1 = 28.68 at 14:00 | **High** |
| Disk presented as rotational virtual HDD | `lsblk` `ROTA=1`, model `QEMU HARDDISK`, hypervisor KVM | **High** |
| Host rebooted twice on 2026-07-11 | `last -x` / `sar` `LINUX RESTART` at **11:25:32** and **19:24:45** | **High** |
| After morning reboot, production UI build was missing | `corpsite-frontend`: repeated `production build missing (.../.next/BUILD_ID)` from 11:25 until first `build OK` at **12:24:27** | **High** |
| Multiple frontend rebuilds completed around the afternoon spike | `build OK` + restart: **13:26**, **13:50**, **14:00**, **14:07** (distinct `BUILD_ID`s) | **High** |
| Cursor Server was connected during afternoon spike | atop `PRG` at 14:02: `server-main.js`, `bootstrap-fork --type=fileWatcher`, extensionHost lineage under `~/.cursor-server/...` | **High** |
| Cursor file watchers saw mass path deletion at 13:47 | `remoteagent.log` session `20260711T113454`: **179** lines `Watcher shutdown because watched path got deleted` starting 13:47:20 | **High** |
| Cursor indexing was active that day | Indexing log: ~1213 embeddable files; periodic re-sync; at 13:32 codebase `STATUS_OUT_OF_SYNC` and merkle compute jumped ~25ms → ~491ms | **High** |
| Page scanning exploded during spike | atop `PAG`: quiet 13:22 ≈ 0 scans; 13:52 ≈ 2.1e6; 14:02 ≈ 1.05e7; 14:12 ≈ 2.11e7 | **High** |
| Memory pressure present at peak | `sar -r` 14:00: `%commit≈104%`, free mem ~0.9 GiB | **High** |
| Docker network I/O was low during peak | `sar -n DEV` 14:00–14:10: docker/veth rates ≪ host disk read bandwidth | **Medium–High** |

### Hypotheses (not fully proven)

| Hypothesis | Why plausible | Why not proven | Confidence |
|------------|---------------|----------------|------------|
| Concurrent `npm run build` / Next compile was the primary physical reader | New `BUILD_ID`s exactly bracket the IOPS ramp; watcher deletes at 13:47 match `.next` wipe | Short-lived build PIDs not captured in 10-min atop process samples | **Medium–High** |
| Cursor `fileWatcher` + indexing amplified reads by rescanning churn under `.next` / workspace | 179 watcher-delete events; live `fileWatcher` PID; indexing OUT_OF_SYNC near build window | No per-path I/O accounting tying bytes to watcher | **Medium** |
| Page-cache thrashing converted write-heavy build into read IOPS storm | High `PAG` scan + `%commit>100%` + read-dominated `sar` | No blktrace / eBPF to attribute re-reads | **Medium** |
| Morning outage was the same class of I/O storm | Same day; `.next` missing after reboot suggests interrupted build | Pre-11:25 `sar` average not as extreme as 14:00 window; kernel OOM lines not found | **Low–Medium** |
| Evening 19:24 reboot was recovery / operator action after lingering instability | Reboot after afternoon incident day | No matching IOPS spike in `sar` 14:20–19:24; no shutdown reason in remaining journal | **Low** (cause of reboot itself unknown) |
| PostgreSQL was a major contributor | Always-on; some PRD stdio bytes on postgres processes | Peak is not write-heavy; docker net quiet; no query-log correlation | **Low** |

---

## 3. Timeline (UTC, 2026-07-11)

| Time (UTC) | Event | Source |
|------------|-------|--------|
| ~03:20–10:49 | Cursor remote session `20260711T032059` active / reconnecting | `~/.cursor-server/data/logs/20260711T032059/remoteagent.log` |
| 10:47–10:49 | Cursor reconnect; `No ptyHost heartbeat` warnings | same |
| **11:25:32** | **LINUX RESTART** (kernel 6.8.0-134) | `sar`, `last -x` |
| 11:25 → ~12:20 | Frontend fails: **`.next/BUILD_ID` missing**; healthcheck fails repeatedly | `journalctl -u corpsite-frontend` |
| 11:34 | New Cursor session `20260711T113454` starts; indexing ~1213 files | Cursor logs |
| **12:24:27** | First post-reboot `build OK` (`BUILD_ID=QqkMDK-...`); frontend starts | frontend journal |
| 12:xx–13:xx | Cursor indexing cycles every ~8 minutes (mostly `UP_TO_DATE`) | Indexing log |
| 13:26:02 | Another `build OK` (`BUILD_ID=hpqn1pt...`) + frontend restart | frontend journal |
| 13:32 | Indexing `STATUS_OUT_OF_SYNC`; merkle time ~491ms (was ~25ms) | Indexing log |
| 13:44–13:46 | Grep/index refresh; agent greps in workspace | Grep Service log |
| **13:47:20–13:48:50** | **≥179 File Watcher “watched path got deleted”** | `remoteagent.log` |
| **13:50:01** | `build OK` (`dOvG7W2t...`) + frontend restart | frontend journal |
| **13:50** | Disk already elevated: sda `tps≈113`, `rkB/s≈7.2MB/s`, `await≈90ms` | `sar -d` |
| **14:00:07** | **Peak window A:** `r/s≈665`, `rkB/s≈61MB/s`, `await≈177`, `aqu-sz≈118`, `%iowait≈44`, load≈28.7 | `sar` |
| **14:00:14** | `build OK` (`ouSo7jjz...`) + frontend restart | frontend journal |
| **14:02 / 14:12** | atop DSK confirms high read load; PAG scan rates extreme | `atop` archive |
| **14:07:48** | `build OK` (`XK8pi0CJ...`) + frontend restart | frontend journal |
| **14:10:02** | **Peak window B:** `r/s≈837`, `rkB/s≈127MB/s`, `await≈189`, `aqu-sz≈158` | `sar` |
| 14:20 | Disk largely recovered (`tps≈44`, `await≈3.5`) | `sar` |
| 14:20–19:24 | No comparable Read IOPS spike in remaining `sar` samples | `sar` |
| **19:24:45** | **LINUX RESTART** again | `sar` / `last` |
| 19:37+ | Cursor session `20260711T193713` after reboot | Cursor logs |

Observed user symptoms (ping OK, SSH TCP accepts but no banner, VNC unusable, nginx/frontend down) are **consistent with** extreme iowait / disk queue latency starving userspace (including `sshd` banner write and nginx). That causal chain is **inferred from system state**, not directly traced per-connection.

---

## 4. Evidence detail

### 4.1 sysstat (`/var/log/sysstat/sa11`)

Afternoon spike (matches PS.kz figures):

```text
02:00:07 PM  sda  tps=665.03  rkB/s=61006.76  wkB/s=2978.14  aqu-sz=118.31  await=177.45  %util=51.35
02:10:02 PM  sda  tps=837.37  rkB/s=127325.70 wkB/s=1343.70  aqu-sz=158.32  await=188.88  %util=48.88
```

Note: `%util` ~50% with huge `aqu-sz`/`await` is typical of **queueing behind an IOPS/latency ceiling**, not “disk idle”.

### 4.2 atop (`/var/log/atop/atop_20260711`)

- Sample interval **600s**.
- DSK at 14:02 / 14:12: elevated read counts (aligns with sar).
- Processes present at 14:02 include:
  - Cursor: `server-main.js`, `fileWatcher`, extensionHost (`bootstrap-fork`)
  - App: `next`/node frontend lineage (service restarted around this time), `uvicorn`, `postgres`, `dockerd`/`containerd`
- **Limitation:** PRD shows `stdio=y` — counters are cumulative syscall I/O, **not reliable physical disk attribution**. Short-lived build processes can exit between 10-minute samples.

### 4.3 Cursor Server behavior (this host)

Observed components (live and in logs):

| Component | Role on remote Linux workspace | Observed |
|-----------|--------------------------------|----------|
| `server-main.js` | Cursor Server | Yes |
| `fileWatcher` | Recursive FS watch on workspace | Yes (PID present; 179 delete storms) |
| `extensionHost` | Extensions + agent | Yes |
| Cursor Indexing & Retrieval | Merkle + embed sync (~1213 files) | Yes |
| Cursor Grep Service | Content search | Yes (agent queries) |
| TypeScript language features | TS server | Present in session; limited log signal in spike window |
| `~/.cursor-server` | Server binaries + data | **~2.0 GiB** (`bin` ~1.9 GiB) |

Indexing appears to target **source-sized** corpus (~1.2k embeddable files), **not** the full 47k tree (which includes `node_modules` ~24k files). That does **not** mean watchers ignore `.next` / `node_modules` for FS events.

**No `.cursorignore` exists** in the repo root or `corpsite-ui/`.

Workspace size drivers (approx.):

| Path | Size / files |
|------|----------------|
| `corpsite-ui/node_modules` | ~660 MiB / ~24k files |
| `.venv` | ~251 MiB / ~10k files |
| `.git` | ~104 MiB / ~10k files |
| `corpsite-ui/.next` | varies (build artifact; wiped/rebuilt) |
| Entire workspace file count | ~47k files |

### 4.4 Build / frontend

`corpsite-frontend` only starts when `.next/BUILD_ID` exists (`check_frontend_build.sh`).

Rebuild cadence on the incident day (completed builds visible as service start):

1. 12:24 — recovery build after missing artifact  
2. 13:26 — rebuild  
3. 13:50 — rebuild (IOPS ramp begins in same 10-min bucket)  
4. 14:00 — rebuild (peak A)  
5. 14:07 — rebuild (peak B)

This is **production builds on the live VPS**, overlapping Cursor remote work.

Stage-level disk profiling (tsc vs webpack vs static generation) was **not measured live** during the incident (no `iotop`/`bpftrace` capture). Inference only:

- Next production build reads large portions of `node_modules` and writes `.next`.
- Cleaning/recreating `.next` produces the watcher-delete pattern seen at 13:47.

### 4.5 PostgreSQL / Docker

- Postgres runs in Docker on this host.
- During 14:00–14:10, Docker/veth packet/byte rates are small relative to host disk read bandwidth.
- **Conclusion:** Postgres/Docker may contribute baseline I/O but are **not evidenced as the spike primary**. Confidence: **Medium–High** for “not primary”, **Low** for “zero contribution”.

### 4.6 Morning incident

- Reboot at 11:25.
- Immediately afterward, `.next` absent → frontend cannot start (~1 hour of failed starts until 12:24).
- Pre-reboot `sar` averages in 09:00–11:25 are **not** as extreme as the afternoon peak (limited forensic resolution).
- Kernel OOM killer lines were **not** found for the morning window in available journal/dmesg excerpts.

**Best-supported morning narrative (hypothesis):** an interrupted on-box build (or manual wipe of `.next`) left the UI without a build artifact across reboot; availability failure followed. Whether Read IOPS caused the reboot itself is **unproven**.

### 4.7 Evening reboot (19:24)

- Hard reboot occurred.
- No matching Read IOPS spike in `sar` after 14:20.
- Cause (provider action, hang, manual) **unknown** from remaining logs.

---

## 5. Process analysis conclusions

### What generated disk reads?

**Most likely combined stack (ranked):**

1. **Next.js production build I/O** on the same disk as production services — **Medium–High** confidence as primary generator.  
2. **Page-cache reclaim re-reads** under memory commit pressure — **Medium** confidence as amplifier of *Read* IOPS.  
3. **Cursor fileWatcher / indexing reacting to build churn** — **Medium** confidence as amplifier / concurrent load.  
4. **PostgreSQL/Docker** — **Low** confidence as spike primary.  

### Did npm build and Cursor overlap?

**Yes — proven overlap in time.**

- Cursor session `20260711T113454` spans the afternoon builds.
- `fileWatcher` process present at 14:02.
- Watcher mass-delete at 13:47 immediately precedes the 13:50/14:00/14:07 build completions and the IOPS peak.

### Root cause statement (careful)

**Proven root symptom:** virtual disk Read IOPS / latency saturation.  

**Most probable root *driver*:** on-VPS frontend production builds (repeated) while Cursor remote tooling watched the same workspace, under memory pressure that amplified reads — on an IOPS-weak virtual HDD volume.

This is a **multi-factor** conclusion. A future incident should capture `pidstat -d`, `iotop`, or `bpftrace` during build to elevate process attribution from Medium–High to High.

---

## 6. Gaps / instrumentation to add (future, not applied now)

1. Retain `pidstat -d 1` / `iotop -bo` during deploy windows.  
2. Shorter atop interval (e.g. 60s) on this host.  
3. Explicit deploy journal markers: build start/end, `du` of `.next` before/after.  
4. Cursor: add `.cursorignore` and watcher excludes (see Guardrails doc).  
5. Confirm with PS.kz the volume’s **IOPS quota** and whether `ROTA=1` maps to HDD-class backing.

---

## 7. Confidence legend used above

| Level | Meaning |
|-------|---------|
| High | Direct metrics/logs; reproducible from archives on this host |
| Medium–High | Strong temporal + mechanistic correlation; missing per-PID disk trace |
| Medium | Plausible mechanism with partial evidence |
| Low–Medium | Consistent but weak/missing pre-event metrics |
| Low | Speculative or contradicted by some data |
