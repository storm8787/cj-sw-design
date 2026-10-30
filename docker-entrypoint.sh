#!/bin/sh
# 배포 서비스의 영속 디스크(Render Disk, Fly Volume 등)는 root 소유로 붙는 경우가 많다.
# root로 시작했으면 DATA_DIR 소유자를 app으로 맞춘 뒤 app 사용자로 낮춰 서버를 실행한다.
set -e
D="${DATA_DIR:-/data}"
if [ "$(id -u)" = "0" ]; then
  mkdir -p "$D"
  if [ "$(stat -c %u "$D")" != "$(id -u app)" ]; then
    chown -R app:app "$D"
  fi
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
