#!/usr/bin/env bash
# CPU, memory and database connections per role, read from /proc (no Docker), for
# docs/STECKBRIEF.md (plan M9 Task 10).
#
#   bash deploy/scripts/measure-processes.sh sample OUT PHASE SECONDS INTERVAL ROLE=PID…
#   bash deploy/scripts/measure-processes.sh summary OUT
#
# sample: every INTERVAL seconds for SECONDS, one line per role is appended to OUT:
#   phase<TAB>role<TAB>cpu %<TAB>RSS MiB<TAB>database connections
# CPU is the process's user + system time since the previous sample (100 % = one core);
# RSS is VmRSS; the connections are the process's own TCP sockets to PGPORT (default
# 5433), found through /proc/PID/fd and /proc/PID/net/tcp{,6}.
# With MEASURE_PG_DB set, a line for role "db" is added: the PostgreSQL backends serving
# that database (pg_stat_activity, through psql and the PG* variables), their summed
# CPU (a backend that started within the interval counts with all its time, one that
# ended loses its last interval), their summed proportional set size (Pss, shared
# memory counted in shares) and their number. A line for role "machine" gives the busy
# share of all CPUs (/proc/stat, 100 % = one core, so 400 % on four cores) and the
# 1-minute load average in place of the memory column.
# summary: per phase and role the number of samples and average/maximum of each column.
set -euo pipefail

pg_port="${PGPORT:-5433}"
tick="$(getconf CLK_TCK)"
port_hex="$(printf '%04X' "$pg_port")"

cpu_ticks() {  # pid…: summed utime+stime in clock ticks
  local total=0 pid fields
  for pid in "$@"; do
    # after the command name; a backend may end between listing and reading
    fields="$(sed 's/^.*) //' "/proc/$pid/stat" 2>/dev/null)" || continue
    total=$((total + $(awk '{print $12 + $13}' <<<"$fields")))
  done
  echo "$total"
}

rss_mib() { awk '/^VmRSS:/ {printf "%.1f", $2 / 1024}' "/proc/$1/status" 2>/dev/null || echo 0; }

pss_mib() {  # pid…: summed Pss in MiB
  local pid kib=0
  for pid in "$@"; do
    kib=$((kib + $(awk '/^Pss:/ {print $2; exit}' "/proc/$pid/smaps_rollup" 2>/dev/null || echo 0)))
  done
  awk -v k="$kib" 'BEGIN {printf "%.1f", k / 1024}'
}

db_connections() {  # pid: established TCP sockets of this process to PGPORT
  local pid=$1 inodes
  inodes="$(find "/proc/$pid/fd" -maxdepth 1 -lname 'socket:*' -printf '%l\n' 2>/dev/null \
    | sed -n 's/^socket:\[\([0-9]*\)\]$/\1/p' | sort -u)"
  [[ -n $inodes ]] || { echo 0; return; }
  cat "/proc/$pid/net/tcp" "/proc/$pid/net/tcp6" 2>/dev/null | awk -v port="$port_hex" '
    NR == FNR { want[$1] = 1; next }
    $4 == "01" { split($3, remote, ":"); if (remote[2] == port && ($10 in want)) n++ }
    END { print n + 0 }' <(echo "$inodes") -
}

db_backends() {
  psql -XAtq -d "${MEASURE_PG_DB}" -c \
    "select pid from pg_stat_activity where datname = '${MEASURE_PG_DB}' and pid <> pg_backend_pid()"
}

machine_ticks() {  # "busy total" over all CPUs, in clock ticks
  awk '/^cpu / {total = 0; for (i = 2; i <= NF; i++) total += $i; print total - $5 - $6, total}' /proc/stat
}

percent() {  # ticks, wall seconds from, to
  awk -v t="$1" -v hz="$tick" -v a="$2" -v b="$3" 'BEGIN {printf "%.1f", 100 * t / hz / (b - a)}'
}

sample() {
  local out=$1 phase=$2 seconds=$3 interval=$4
  shift 4
  local -A pid_of=() before=() backend_ticks=() seen=()
  local role spec start now elapsed_ticks wall_before wall_now pid ticks busy total
  local -a backends=() machine_before machine_now
  for spec in "$@"; do pid_of[${spec%%=*}]=${spec#*=}; done
  for role in "${!pid_of[@]}"; do before[$role]=$(cpu_ticks "${pid_of[$role]}"); done
  if [[ -n ${MEASURE_PG_DB:-} ]]; then
    mapfile -t backends < <(db_backends)
    for pid in "${backends[@]}"; do backend_ticks[$pid]=$(cpu_ticks "$pid"); done
  fi
  read -ra machine_before < <(machine_ticks)
  wall_before=$(date +%s.%N)
  start=$(date +%s)
  while (( $(date +%s) - start < seconds )); do
    sleep "$interval"
    wall_now=$(date +%s.%N)
    for role in "${!pid_of[@]}"; do
      now=$(cpu_ticks "${pid_of[$role]}")
      elapsed_ticks=$((now - before[$role]))
      before[$role]=$now
      printf '%s\t%s\t%s\t%s\t%s\n' "$phase" "$role" \
        "$(percent "$elapsed_ticks" "$wall_before" "$wall_now")" \
        "$(rss_mib "${pid_of[$role]}")" "$(db_connections "${pid_of[$role]}")" >>"$out"
    done
    if [[ -n ${MEASURE_PG_DB:-} ]]; then
      mapfile -t backends < <(db_backends)
      elapsed_ticks=0
      seen=()
      for pid in "${backends[@]}"; do
        ticks=$(cpu_ticks "$pid")
        elapsed_ticks=$((elapsed_ticks + ticks - ${backend_ticks[$pid]:-0}))
        seen[$pid]=$ticks
      done
      backend_ticks=()
      for pid in "${!seen[@]}"; do backend_ticks[$pid]=${seen[$pid]}; done
      printf '%s\tdb\t%s\t%s\t%s\n' "$phase" "$(percent "$elapsed_ticks" "$wall_before" "$wall_now")" \
        "$(pss_mib "${backends[@]}")" "${#backends[@]}" >>"$out"
    fi
    read -ra machine_now < <(machine_ticks)
    busy=$((machine_now[0] - machine_before[0])) total=$((machine_now[1] - machine_before[1]))
    machine_before=("${machine_now[@]}")
    printf '%s\tmachine\t%s\t%s\t0\n' "$phase" \
      "$(awk -v b="$busy" -v t="$total" -v n="$(nproc)" 'BEGIN {printf "%.1f", t ? 100 * n * b / t : 0}')" \
      "$(cut -d' ' -f1 /proc/loadavg)" >>"$out"
    wall_before=$wall_now
  done
}

summary() {
  printf '%-10s %-10s %4s %8s %8s %8s %8s %6s %6s\n' \
    phase role n 'cpu avg' 'cpu max' 'MiB avg' 'MiB max' 'db avg' 'db max'
  awk -F'\t' '
    !(($1, $2) in n) { order[++k] = $1 SUBSEP $2 }
    { key = $1 SUBSEP $2; n[key]++; cpu[key] += $3; mem[key] += $4; db[key] += $5
      if ($3 > cmax[key]) cmax[key] = $3; if ($4 > mmax[key]) mmax[key] = $4
      if ($5 > dmax[key]) dmax[key] = $5 }
    END { for (i = 1; i <= k; i++) { key = order[i]; split(key, part, SUBSEP)
      printf "%-10s %-10s %4d %7.1f%% %7.1f%% %8.1f %8.1f %6.1f %6d\n", part[1], part[2],
        n[key], cpu[key] / n[key], cmax[key], mem[key] / n[key], mmax[key],
        db[key] / n[key], dmax[key] } }' "$1"
}

case "${1:-}" in
  sample) [[ $# -ge 6 ]] || { sed -n '2,20p' "$0"; exit 2; }; shift; sample "$@" ;;
  summary) [[ $# -eq 2 ]] || { sed -n '2,20p' "$0"; exit 2; }; summary "$2" ;;
  *) sed -n '2,20p' "$0"; exit 2 ;;
esac
