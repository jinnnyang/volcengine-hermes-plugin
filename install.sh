#!/bin/sh
# install.sh - Install Volcengine plugins to a Hermes Agent profile.

set -e

DEFAULT_ENABLE_MODEL=1
DEFAULT_ENABLE_IMAGE=1
DEFAULT_ENABLE_VIDEO=1
DEFAULT_ENABLE_WEB_SEARCH=1
DEFAULT_ENABLE_TTS=1
DEFAULT_ENABLE_STT=1

ENABLE_MODEL=$DEFAULT_ENABLE_MODEL
ENABLE_IMAGE=$DEFAULT_ENABLE_IMAGE
ENABLE_VIDEO=$DEFAULT_ENABLE_VIDEO
ENABLE_WEB_SEARCH=$DEFAULT_ENABLE_WEB_SEARCH
ENABLE_TTS=$DEFAULT_ENABLE_TTS
ENABLE_STT=$DEFAULT_ENABLE_STT
SET_DEFAULT_WEB_SEARCH=1
SET_DEFAULT_TTS=1
SET_DEFAULT_STT=1
NO_CONFIG=0
DRY_RUN=0
PROFILE=""
MODE=""
BASE_URL=""

usage() {
  cat <<'EOF'
Usage: bash install.sh [options]

Install Volcengine provider plugins into a Hermes Agent profile.

Options:
  --profile PATH              Target Hermes profile directory. If omitted, scan and prompt.
  --mode agent|coding|api      Set VOLCENGINE_PLAN_MODE in the profile .env.
  --base-url URL              Set VOLCENGINE_BASE_URL in the profile .env.

  --enable-model              Install/enable model provider plugin. Default: enabled.
  --enable-image              Install/enable image generation plugin. Default: enabled.
  --enable-video              Install/enable video generation plugin. Default: enabled.
  --enable-web-search         Install/enable web search plugin. Default: enabled.
  --enable-tts                Install/enable TTS plugin. Default: enabled.
  --enable-stt                Install/enable STT/transcription plugin. Default: enabled.

  --no-model                  Do not install/enable model provider plugin.
  --no-image                  Do not install/enable image generation plugin.
  --no-video                  Do not install/enable video generation plugin.
  --no-web-search             Do not install/enable web search plugin.
  --no-tts                    Do not install/enable TTS plugin.
  --no-stt                    Do not install/enable STT/transcription plugin.

  --set-default-web-search    Set web.search_backend=volcengine. Default: enabled.
  --no-default-web-search     Do not change web.search_backend.
  --set-default-tts           Set tts.provider=volcengine. Default: enabled.
  --no-default-tts            Do not change tts.provider.
  --set-default-stt           Set stt.enabled=true and stt.provider=volcengine. Default: enabled.
  --no-default-stt            Do not change stt.provider.

  --no-config                 Copy plugins only; do not edit config.yaml or .env.
  --dry-run                   Print actions without changing files.
  -h, --help                  Show this help.

Secrets are never written to config.yaml. Put API keys in the target profile .env:
  VOLCENGINE_API_KEY=[REDACTED]
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --profile)
      PROFILE=${2:-}
      shift 2
      ;;
    --mode)
      MODE=${2:-}
      shift 2
      ;;
    --base-url)
      BASE_URL=${2:-}
      shift 2
      ;;
    --enable-model) ENABLE_MODEL=1; shift ;;
    --enable-image) ENABLE_IMAGE=1; shift ;;
    --enable-video) ENABLE_VIDEO=1; shift ;;
    --enable-web-search) ENABLE_WEB_SEARCH=1; shift ;;
    --enable-tts) ENABLE_TTS=1; shift ;;
    --enable-stt) ENABLE_STT=1; shift ;;
    --no-model) ENABLE_MODEL=0; shift ;;
    --no-image) ENABLE_IMAGE=0; shift ;;
    --no-video) ENABLE_VIDEO=0; shift ;;
    --no-web-search) ENABLE_WEB_SEARCH=0; shift ;;
    --no-tts) ENABLE_TTS=0; shift ;;
    --no-stt) ENABLE_STT=0; shift ;;
    --set-default-web-search) SET_DEFAULT_WEB_SEARCH=1; shift ;;
    --no-default-web-search) SET_DEFAULT_WEB_SEARCH=0; shift ;;
    --set-default-tts) SET_DEFAULT_TTS=1; shift ;;
    --no-default-tts) SET_DEFAULT_TTS=0; shift ;;
    --set-default-stt) SET_DEFAULT_STT=1; shift ;;
    --no-default-stt) SET_DEFAULT_STT=0; shift ;;
    --no-config) NO_CONFIG=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "[!] Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

case "$MODE" in
  ""|agent|coding|api) ;;
  *) echo "[!] --mode must be one of: agent, coding, api"; exit 1 ;;
esac

run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

copy_tree() {
  src=$1
  dest=$2
  if [ ! -d "$src" ]; then
    echo "[!] Source $src not found. Run this script from the repository root."
    exit 1
  fi
  echo "--> Copying $src -> $dest"
  run mkdir -p "$dest"
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] cp -r $src/* $dest/"
  else
    cp -r "$src"/* "$dest"/
  fi
}

# Python updater edits only non-secret config.yaml settings.
PYTHON_UPDATER=$(cat << 'EOF'
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required to update config.yaml") from exc

config_path = Path(sys.argv[1])
enabled_plugins = [item for item in sys.argv[2].split(",") if item]
set_web = sys.argv[3] == "1"
set_tts = sys.argv[4] == "1"
set_stt = sys.argv[5] == "1"

backup_path = config_path.with_name(config_path.name + ".volcengine-backup")
shutil.copy2(config_path, backup_path)

with config_path.open("r", encoding="utf-8") as fh:
    config = yaml.safe_load(fh) or {}

plugins = config.setdefault("plugins", {})
current_enabled = plugins.get("enabled")
if not isinstance(current_enabled, list):
    current_enabled = []
plugins["enabled"] = sorted(set([str(item) for item in current_enabled] + enabled_plugins))

# Clean up legacy misspelled plugin keys.
plugins["enabled"] = [
    item for item in plugins["enabled"]
    if item not in {"image_gen/volces-engine", "video_gen/volces-engine", "model-providers/volces-engine"}
]

if "model-providers/volcengine" in enabled_plugins:
    model = config.setdefault("model", {})
    model["provider"] = "volcengine"

if "image_gen/volcengine" in enabled_plugins:
    image = config.setdefault("image_gen", {})
    image["provider"] = "volcengine"
    image.setdefault("model", "doubao-seedream-5.0-lite")

if "video_gen/volcengine" in enabled_plugins:
    video = config.setdefault("video_gen", {})
    video["provider"] = "volcengine"
    video.setdefault("model", "doubao-seedance-1.5-pro")

if set_web:
    web = config.setdefault("web", {})
    web["search_backend"] = "volcengine"
    web.setdefault("backend", "volcengine")

if set_tts:
    tts = config.setdefault("tts", {})
    tts["provider"] = "volcengine"
    volc_tts = tts.setdefault("volcengine", {})
    volc_tts.setdefault("model", "doubao-seed-tts-2.0")
    volc_tts.setdefault("voice", "zh_female_vv_uranus_bigtts")
    volc_tts.setdefault("format", "wav")
    volc_tts.setdefault("sample_rate", 24000)

if set_stt:
    stt = config.setdefault("stt", {})
    stt["enabled"] = True
    stt["provider"] = "volcengine"
    volc_stt = stt.setdefault("volcengine", {})
    volc_stt.setdefault("model", "doubao-seed-asr-2.0")
    volc_stt.setdefault("language", "auto")

with config_path.open("w", encoding="utf-8") as fh:
    yaml.safe_dump(config, fh, allow_unicode=True, sort_keys=False)

print(f"backup={backup_path}")
EOF
)

ENV_UPDATER=$(cat << 'EOF'
import sys
from pathlib import Path

env_path = Path(sys.argv[1])
mode = sys.argv[2]
base_url = sys.argv[3]
updates = {}
if mode:
    updates["VOLCENGINE_PLAN_MODE"] = mode
if base_url:
    updates["VOLCENGINE_BASE_URL"] = base_url

existing = []
if env_path.exists():
    existing = env_path.read_text(encoding="utf-8").splitlines()

seen = set()
out = []
for line in existing:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

env_path.parent.mkdir(parents=True, exist_ok=True)
env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
EOF
)

find_hermes_homes() {
  candidates=""
  if [ -d "/opt/data/profiles" ]; then candidates="$candidates /opt/data/profiles"; fi
  if [ -d "$HOME/.hermes" ]; then candidates="$candidates $HOME/.hermes"; fi
  if [ -d "$HOME/AppData/Local/hermes/profiles" ]; then candidates="$candidates $HOME/AppData/Local/hermes/profiles"; fi
  if [ -d "/c/Users/$USER/AppData/Local/hermes/profiles" ]; then candidates="$candidates /c/Users/$USER/AppData/Local/hermes/profiles"; fi
  if [ -d "/root/.hermes" ]; then candidates="$candidates /root/.hermes"; fi
  if [ -n "$HERMES_HOME" ] && [ -d "$HERMES_HOME" ]; then candidates="$candidates $HERMES_HOME"; fi

  found_dirs=""
  for base in $candidates; do
    if [ -f "$base/config.yaml" ]; then
      found_dirs="$found_dirs
$base"
    fi
    for cfg in "$base"/*/config.yaml; do
      if [ -f "$cfg" ]; then
        dir="${cfg%/config.yaml}"
        found_dirs="$found_dirs
$dir"
      fi
    done
  done

  echo "$found_dirs" | tr -d '\r' | sort -u | grep -v '^$'
}

show_manual_instructions() {
  cat <<'EOF'
==================================================================
                  MANUAL INSTALLATION INSTRUCTIONS
==================================================================
1. Copy the plugin folders to your Hermes profile's plugins directory:
   cp -r plugins/_volcengine_common [HERMES_HOME]/plugins/
   cp -r plugins/model-providers/volcengine [HERMES_HOME]/plugins/model-providers/
   cp -r plugins/image_gen/volcengine [HERMES_HOME]/plugins/image_gen/
   cp -r plugins/video_gen/volcengine [HERMES_HOME]/plugins/video_gen/
   cp -r plugins/web/volcengine [HERMES_HOME]/plugins/web/
   cp -r plugins/tts/volcengine [HERMES_HOME]/plugins/tts/
   cp -r plugins/transcription/volcengine [HERMES_HOME]/plugins/transcription/

2. Enable the plugin registry keys in [HERMES_HOME]/config.yaml:
   plugins:
     enabled:
       - model-providers/volcengine
       - image_gen/volcengine
       - video_gen/volcengine
       - web/volcengine
       - tts/volcengine
       - transcription/volcengine

3. Configure active providers in [HERMES_HOME]/config.yaml:
   model:
     provider: volcengine

   web:
     search_backend: volcengine

   image_gen:
     provider: volcengine
     model: doubao-seedream-5.0-lite

   video_gen:
     provider: volcengine
     model: doubao-seedance-1.5-pro

   tts:
     provider: volcengine
     volcengine:
       model: doubao-seed-tts-2.0
       voice: zh_female_vv_uranus_bigtts
       format: wav
       sample_rate: 24000

   stt:
     enabled: true
     provider: volcengine
     volcengine:
       model: doubao-seed-asr-2.0
       language: auto

4. Put secrets in [HERMES_HOME]/.env, never in config.yaml:
   VOLCENGINE_API_KEY=[REDACTED]
==================================================================
EOF
}

if [ -n "$PROFILE" ]; then
  chosen_home=$PROFILE
else
  echo "Scanning for Hermes Agent profile directories..."
  homes=$(find_hermes_homes)
  if [ -z "$homes" ]; then
    echo "[-] No Hermes Agent profile directories detected."
    echo ""
    show_manual_instructions
    exit 0
  fi

  echo "Found the following Hermes Agent profile directories:"
  i=1
  echo "$homes" | while read -r line; do
    echo "  [$i] $line"
    i=$((i + 1))
  done

  num_homes=$(echo "$homes" | wc -l | tr -d ' ')
  echo ""
  if [ "$num_homes" -eq 1 ]; then default_prompt="[1]"; else default_prompt="1-$num_homes"; fi
  printf "Select a profile directory to install the plugins ($default_prompt, or press Enter for [1]): "
  read -r selection
  selection=$(echo "$selection" | tr -d '\r')
  if [ -z "$selection" ]; then selection=1; fi
  if ! echo "$selection" | grep -qE '^[0-9]+$' || [ "$selection" -lt 1 ] || [ "$selection" -gt "$num_homes" ]; then
    echo "[!] Invalid selection '$selection'. Installation aborted."
    echo ""
    show_manual_instructions
    exit 1
  fi
  chosen_home=$(echo "$homes" | sed -n "${selection}p" | tr -d '\r')
fi

if [ ! -f "$chosen_home/config.yaml" ]; then
  echo "[!] $chosen_home does not look like a Hermes profile: config.yaml not found."
  exit 1
fi

echo "[+] Installing to profile: $chosen_home"

# Clean up older misspelled plugin directories.
for old in \
  "$chosen_home/plugins/model-providers/volces-engine" \
  "$chosen_home/plugins/image_gen/volces-engine" \
  "$chosen_home/plugins/video_gen/volces-engine"; do
  if [ -d "$old" ]; then
    echo "--> Cleaning up older profile plugin $old"
    run rm -rf "$old"
  fi
done

enabled_keys=""
append_key() {
  if [ -z "$enabled_keys" ]; then enabled_keys="$1"; else enabled_keys="$enabled_keys,$1"; fi
}

# Copy shared support package used by every Volcengine plugin.
copy_tree "plugins/_volcengine_common" "$chosen_home/plugins/_volcengine_common"

if [ "$ENABLE_MODEL" -eq 1 ]; then
  copy_tree "plugins/model-providers/volcengine" "$chosen_home/plugins/model-providers/volcengine"
  append_key "model-providers/volcengine"
fi
if [ "$ENABLE_IMAGE" -eq 1 ]; then
  copy_tree "plugins/image_gen/volcengine" "$chosen_home/plugins/image_gen/volcengine"
  append_key "image_gen/volcengine"
fi
if [ "$ENABLE_VIDEO" -eq 1 ]; then
  copy_tree "plugins/video_gen/volcengine" "$chosen_home/plugins/video_gen/volcengine"
  append_key "video_gen/volcengine"
fi
if [ "$ENABLE_WEB_SEARCH" -eq 1 ]; then
  copy_tree "plugins/web/volcengine" "$chosen_home/plugins/web/volcengine"
  append_key "web/volcengine"
fi
if [ "$ENABLE_TTS" -eq 1 ]; then
  copy_tree "plugins/tts/volcengine" "$chosen_home/plugins/tts/volcengine"
  append_key "tts/volcengine"
fi
if [ "$ENABLE_STT" -eq 1 ]; then
  copy_tree "plugins/transcription/volcengine" "$chosen_home/plugins/transcription/volcengine"
  append_key "transcription/volcengine"
fi

if [ "$NO_CONFIG" -eq 0 ]; then
  effective_web=$SET_DEFAULT_WEB_SEARCH
  effective_tts=$SET_DEFAULT_TTS
  effective_stt=$SET_DEFAULT_STT
  if [ "$ENABLE_WEB_SEARCH" -eq 0 ]; then effective_web=0; fi
  if [ "$ENABLE_TTS" -eq 0 ]; then effective_tts=0; fi
  if [ "$ENABLE_STT" -eq 0 ]; then effective_stt=0; fi

  echo "--> Updating config.yaml with enabled plugins and provider defaults..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] update $chosen_home/config.yaml; backup would be created"
  else
    python3 -c "$PYTHON_UPDATER" "$chosen_home/config.yaml" "$enabled_keys" "$effective_web" "$effective_tts" "$effective_stt" 2>/dev/null || \
      python -c "$PYTHON_UPDATER" "$chosen_home/config.yaml" "$enabled_keys" "$effective_web" "$effective_tts" "$effective_stt" || {
        echo "[!] Warning: Python configuration updater failed. You will need to edit config.yaml manually."
      }
  fi

  if [ -n "$MODE" ] || [ -n "$BASE_URL" ]; then
    echo "--> Updating non-secret Volcengine endpoint settings in .env..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[dry-run] update $chosen_home/.env with VOLCENGINE_PLAN_MODE/VOLCENGINE_BASE_URL"
    else
      python3 -c "$ENV_UPDATER" "$chosen_home/.env" "$MODE" "$BASE_URL" 2>/dev/null || \
        python -c "$ENV_UPDATER" "$chosen_home/.env" "$MODE" "$BASE_URL" || {
          echo "[!] Warning: .env updater failed. You may need to set VOLCENGINE_PLAN_MODE or VOLCENGINE_BASE_URL manually."
        }
    fi
  fi
else
  echo "--> --no-config set; skipped config.yaml and .env updates."
fi

cat <<EOF

[+] Volcengine plugins installed to $chosen_home.

Next steps:
1. Put secrets in $chosen_home/.env, never in config.yaml:
   VOLCENGINE_API_KEY=[REDACTED]
2. Restart Hermes Agent / reset the session so newly enabled plugins load.
3. Verify with:
   hermes plugins list --plain --enabled

EOF

show_manual_instructions
