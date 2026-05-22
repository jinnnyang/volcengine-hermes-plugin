#!/bin/sh
# install.sh - Install volces-engine plugins to Hermes Agent profile

set -e

# Define python updater code to update config.yaml safely
PYTHON_UPDATER=$(cat << 'EOF'
import sys

def update_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.splitlines()
    in_plugins = False
    in_enabled = False
    
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if stripped == "plugins:":
            in_plugins = True
            in_enabled = False
        elif in_plugins and stripped == "enabled:":
            in_enabled = True
        elif stripped.endswith(":") and not stripped.startswith("-"):
            in_plugins = False
            in_enabled = False
            
        if stripped == "image_gen:":
            new_lines.append(line)
            i += 1
            while i < len(lines):
                subline = lines[i]
                substripped = subline.strip()
                if substripped.startswith("provider:"):
                    indent = " " * (len(subline) - len(subline.lstrip()))
                    new_lines.append(f"{indent}provider: volces-engine")
                    break
                elif substripped.endswith(":") and not substripped.startswith("-"):
                    i -= 1
                    break
                else:
                    new_lines.append(subline)
                i += 1
            i += 1
            continue
            
        if stripped == "video_gen:":
            new_lines.append(line)
            i += 1
            while i < len(lines):
                subline = lines[i]
                substripped = subline.strip()
                if substripped.startswith("provider:"):
                    indent = " " * (len(subline) - len(subline.lstrip()))
                    new_lines.append(f"{indent}provider: volces-engine")
                    break
                elif substripped.endswith(":") and not substripped.startswith("-"):
                    i -= 1
                    break
                else:
                    new_lines.append(subline)
                i += 1
            i += 1
            continue
            
        new_lines.append(line)
        i += 1

    final_lines = []
    in_plugins = False
    in_enabled = False
    has_image_gen_plugin = False
    has_video_gen_plugin = False
    
    for line in new_lines:
        stripped = line.strip()
        if stripped == "plugins:":
            in_plugins = True
            in_enabled = False
        elif in_plugins and stripped == "enabled:":
            in_enabled = True
        elif in_enabled and stripped.startswith("-"):
            val = stripped.split("-")[1].strip()
            if val == "image_gen/volces-engine":
                has_image_gen_plugin = True
            elif val == "video_gen/volces-engine":
                has_video_gen_plugin = True
        elif stripped.endswith(":") and not stripped.startswith("-"):
            in_plugins = False
            in_enabled = False

    in_plugins = False
    in_enabled = False
    for line in new_lines:
        final_lines.append(line)
        stripped = line.strip()
        if stripped == "plugins:":
            in_plugins = True
            in_enabled = False
        elif in_plugins and stripped == "enabled:":
            in_enabled = True
            indent = " " * (len(line) - len(line.lstrip()))
            item_indent = indent + "  "
            if not has_image_gen_plugin:
                final_lines.append(f"{item_indent}- image_gen/volces-engine")
            if not has_video_gen_plugin:
                final_lines.append(f"{item_indent}- video_gen/volces-engine")
        elif stripped.endswith(":") and not stripped.startswith("-"):
            in_plugins = False
            in_enabled = False

    saw_plugins = any(l.strip() == "plugins:" for l in final_lines)
    if not saw_plugins:
        final_lines.append("")
        final_lines.append("plugins:")
        final_lines.append("  enabled:")
        final_lines.append("    - image_gen/volces-engine")
        final_lines.append("    - video_gen/volces-engine")
        
    saw_image_gen = any(l.strip() == "image_gen:" for l in final_lines)
    if not saw_image_gen:
        final_lines.append("")
        final_lines.append("image_gen:")
        final_lines.append("  provider: volces-engine")
        final_lines.append("  model: doubao-seedream-5.0-lite")

    saw_video_gen = any(l.strip() == "video_gen:" for l in final_lines)
    if not saw_video_gen:
        final_lines.append("")
        final_lines.append("video_gen:")
        final_lines.append("  provider: volces-engine")
        final_lines.append("  model: doubao-seedance-2.0")

    with open(config_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(final_lines) + "\n")

if __name__ == '__main__':
    update_config(sys.argv[1])
EOF
)

# Function to search for Hermes Agent home directories
find_hermes_homes() {
  # Candidate base search paths
  candidates=""
  if [ -d "/opt/data/profiles" ]; then
    candidates="$candidates /opt/data/profiles"
  fi
  if [ -d "$HOME/.hermes" ]; then
    candidates="$candidates $HOME/.hermes"
  fi
  if [ -d "/root/.hermes" ]; then
    candidates="$candidates /root/.hermes"
  fi
  if [ -n "$HERMES_HOME" ] && [ -d "$HERMES_HOME" ]; then
    candidates="$candidates $HERMES_HOME"
  fi

  # Find config.yaml files
  found_dirs=""
  for base in $candidates; do
    # check base itself
    if [ -f "$base/config.yaml" ] && [ -f "$base/SOUL.md" ] && [ -e "$base/home" ]; then
      found_dirs="$found_dirs
$base"
    fi
    # search subdirectories recursively
    if command -v find >/dev/null 2>&1; then
      dirs=$(find "$base" -name "config.yaml" 2>/dev/null)
      for cfg in $dirs; do
        dir=$(dirname "$cfg")
        if [ -f "$dir/SOUL.md" ] && [ -e "$dir/home" ]; then
          found_dirs="$found_dirs
$dir"
        fi
      done
    fi
  done

  # output unique sorted directories, stripping any carriage return
  echo "$found_dirs" | tr -d '\r' | sort -u | grep -v '^$'
}

# Function to show manual installation instructions
show_manual_instructions() {
  echo "=================================================================="
  echo "                  MANUAL INSTALLATION INSTRUCTIONS                "
  echo "=================================================================="
  echo "If automatic installation is not possible, please follow these steps:"
  echo ""
  echo "1. Copy the plugin folders to your Hermes profile's plugins directory:"
  echo "   cp -r plugins/model-providers/volces-engine [HERMES_HOME]/plugins/model-providers/"
  echo "   cp -r plugins/image_gen/volces-engine [HERMES_HOME]/plugins/image_gen/"
  echo "   cp -r plugins/video_gen/volces-engine [HERMES_HOME]/plugins/video_gen/"
  echo ""
  echo "2. Edit your [HERMES_HOME]/config.yaml file to enable the plugins:"
  echo "   plugins:"
  echo "     enabled:"
  echo "       - image_gen/volces-engine"
  echo "       - video_gen/volces-engine"
  echo ""
  echo "3. Configure active providers in [HERMES_HOME]/config.yaml:"
  echo "   image_gen:"
  echo "     provider: volces-engine"
  echo "     model: doubao-seedream-5.0-lite"
  echo ""
  echo "   video_gen:"
  echo "     provider: volces-engine"
  echo "     model: doubao-seedance-2.0"
  echo ""
  echo "4. Set up environment variables in your profile's .env file:"
  echo "   ARK_API_KEY=your_api_key_here"
  echo "=================================================================="
}

echo "Scanning for Hermes Agent profile directories..."
homes=$(find_hermes_homes)

if [ -z "$homes" ]; then
  echo "[-] No Hermes Agent profile directories detected containing SOUL.md, config.yaml, and home."
  echo ""
  show_manual_instructions
  exit 0
fi

# Convert list to array-like list
echo "Found the following Hermes Agent profile directories:"
i=1
# Read lines from variable
echo "$homes" | while read -r line; do
  echo "  [$i] $line"
  i=$((i + 1))
done

num_homes=$(echo "$homes" | wc -l | tr -d ' ')
echo ""
if [ "$num_homes" -eq 1 ]; then
  default_prompt="[1]"
else
  default_prompt="1-$num_homes"
fi

printf "Select a profile directory to install the plugins ($default_prompt, or press Enter for [1]): "
read -r selection

# Strip any Windows carriage returns from input
selection=$(echo "$selection" | tr -d '\r')

if [ -z "$selection" ]; then
  selection=1
fi

# Validate selection is a number and within range
if ! echo "$selection" | grep -qE '^[0-9]+$' || [ "$selection" -lt 1 ] || [ "$selection" -gt "$num_homes" ]; then
  echo "[!] Invalid selection '$selection'. Installation aborted."
  echo ""
  show_manual_instructions
  exit 1
fi

# Get the chosen home directory
chosen_home=$(echo "$homes" | sed -n "${selection}p" | tr -d '\r')

echo "[+] Installing to profile: $chosen_home"

# Copy plugin files
echo "--> Creating plugin directories..."
mkdir -p "$chosen_home/plugins/model-providers/volces-engine"
mkdir -p "$chosen_home/plugins/image_gen/volces-engine"
mkdir -p "$chosen_home/plugins/video_gen/volces-engine"

echo "--> Copying plugin files..."
if [ -d "plugins/model-providers/volces-engine" ]; then
  cp -r plugins/model-providers/volces-engine/* "$chosen_home/plugins/model-providers/volces-engine/"
else
  echo "[!] Source plugins/model-providers/volces-engine not found! Make sure you run this script from the workspace root."
  exit 1
fi

if [ -d "plugins/image_gen/volces-engine" ]; then
  cp -r plugins/image_gen/volces-engine/* "$chosen_home/plugins/image_gen/volces-engine/"
else
  echo "[!] Source plugins/image_gen/volces-engine not found!"
  exit 1
fi

if [ -d "plugins/video_gen/volces-engine" ]; then
  cp -r plugins/video_gen/volces-engine/* "$chosen_home/plugins/video_gen/volces-engine/"
else
  echo "[!] Source plugins/video_gen/volces-engine not found!"
  exit 1
fi

# Update configuration using Python
echo "--> Updating config.yaml..."
python3 -c "$PYTHON_UPDATER" "$chosen_home/config.yaml" 2>/dev/null || python -c "$PYTHON_UPDATER" "$chosen_home/config.yaml" || {
  echo "[!] Warning: Python configuration updater failed. You will need to edit config.yaml manually."
}

echo ""
echo "[+] Volcengine (volces-engine) plugins successfully installed to $chosen_home!"
echo ""
show_manual_instructions
