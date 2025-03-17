#!/bin/bash

# Disable "exit on error" for our interactive script
set +e

################################
# CONFIG AND HELPER FUNCTIONS
################################

DEBUG="${DEBUG:-0}"
if [ "$DEBUG" = "1" ]; then
  echo "DEBUG MODE ENABLED"
fi

function debug_log() {
  if [ "$DEBUG" = "1" ]; then
    echo "DEBUG: $1" >&2
  fi
}

################################
# SSH KEY MANAGEMENT FUNCTION
################################

function verify_single_key() {
  # Function to verify only one key is active and fix if needed
  # Returns: name of the active key or empty string if no key is active
  
  local num_keys active_key_info
  
  # Check current keys - use a better approach to count keys
  active_key_info=$(ssh-add -l 2>/dev/null)
  num_keys=$(echo "$active_key_info" | grep -E "SHA256|MD5" | wc -l)
  
  if [ "$num_keys" -eq 0 ]; then
    echo "⚠️ No SSH keys currently active"
    return 1
  elif [ "$num_keys" -gt 1 ]; then
    echo "⚠️ Multiple keys detected ($num_keys keys active)"
    echo "$active_key_info" | sed 's/^/   /'
    
    echo "🔄 Ensuring only the selected key remains active..."
    
    # First clear all keys
    ssh-add -D > /dev/null
    
    # Re-add just the selected key
    if [ -n "$1" ]; then
      echo "🔑 Reactivating only key: $(basename "$1")"
      if ssh-add "$1" &>/dev/null || ssh-add "$1"; then
        # Double-check that we only have one key now
        rechecked_keys=$(ssh-add -l 2>/dev/null | grep -E "SHA256|MD5" | wc -l)
        if [ "$rechecked_keys" -eq 1 ]; then
          echo "✅ Successfully activated single key"
          return 0
        else
          echo "⚠️ Still detected $rechecked_keys keys after cleanup attempt"
          # One more aggressive attempt to fix
          ssh-add -D > /dev/null
          sleep 1
          ssh-add "$1" &>/dev/null || ssh-add "$1"
          return 0
        fi
      else
        echo "❌ Failed to reactivate key"
        return 1
      fi
    else
      echo "❌ No key path provided for reactivation"
      return 1
    fi
  else
    # Exactly one key active - perfect!
    echo "✅ Verified: Single key active"
    return 0
  fi
}

function manage_ssh_keys() {
  # This function handles scanning, displaying, and activating SSH keys
  # Returns: 0 = success, 1 = try again, 2 = fatal error
  
  clear
  echo "┌───────────────────────────────────────────┐"
  echo "│     🔐 GIT SSH AUTHENTICATION SETUP       │"
  echo "└───────────────────────────────────────────┘"
  echo ""
  echo "STEP 3: Managing SSH keys..."
  
  # Debug
  if [ "$DEBUG" = "1" ]; then
    set -x
  fi
  
  # Find all SSH keys in the .ssh directory
  echo "🔍 Scanning for SSH keys..."
  local ssh_keys=()
  for key in ~/.ssh/id_*; do
    # Only include private keys (not .pub files)
    if [[ -f "$key" && ! "$key" =~ \.pub$ && ! "$key" =~ \.bak$ ]]; then
      ssh_keys+=("$key")
    fi
  done
  
  if [ ${#ssh_keys[@]} -eq 0 ]; then
    echo "❌ No SSH keys found in ~/.ssh directory"
    echo "   You may need to set up SSH keys on your host machine"
    return 2  # Fatal error
  fi
  
  # Display available SSH keys
  echo "📋 Available SSH keys:"
  for i in "${!ssh_keys[@]}"; do
    key="${ssh_keys[$i]}"
    key_name=$(basename "$key")
    echo "   $((i+1))) $key_name"
  done
  
  # Show currently loaded keys
  echo ""
  echo "📋 Currently active SSH key:"
  
  # Capture ssh-add output and exit code
  local ssh_add_output ssh_add_exit_code current_key_fingerprint current_key_name
  ssh_add_output=$(ssh-add -l 2>&1) || true
  ssh_add_exit_code=$?
  
  # ssh-add return codes: 0=keys found, 1=no keys, 2=no agent
  if [ $ssh_add_exit_code -eq 0 ] && [[ ! "$ssh_add_output" == *"no identities"* ]]; then
    # Keys found, show them
    echo "$ssh_add_output" | sed 's/^/   /'
    # Get the first loaded key
    current_key_fingerprint=$(echo "$ssh_add_output" | head -1 | awk '{print $2}')
    current_key_name=$(echo "$ssh_add_output" | head -1 | awk '{print $3}')
  else
    # No keys loaded or SSH agent issue
    echo "   None - no key currently active"
    current_key_fingerprint=""
    current_key_name=""
    
    # If agent isn't running, start it
    if [ $ssh_add_exit_code -eq 2 ]; then
      echo "   Starting SSH agent..."
      eval "$(ssh-agent -s)" > /dev/null
    fi
  fi
  
  # Key selection options
  echo ""
  echo "┌────────────────────────────────────────┐"
  echo "│  PLEASE SELECT A KEY OPTION BELOW:     │"
  echo "└────────────────────────────────────────┘"
  echo "📌 KEY ACTIVATION OPTIONS:"
  echo "   • Press ENTER to keep current key (if any)"
  echo "   • Enter a number between 1-${#ssh_keys[@]} to activate that specific key"
  echo "   • Enter 'C' to clear all keys and start fresh"
  echo ""
  echo -n "Your choice [default=keep current]: "
  read key_choice
  echo ""
  
  if [[ "$key_choice" =~ ^[0-9]+$ ]] && [ "$key_choice" -ge 1 ] && [ "$key_choice" -le "${#ssh_keys[@]}" ]; then
    # User selected a specific key by number
    local selected_key="${ssh_keys[$((key_choice-1))]}"
    local selected_key_name=$(basename "$selected_key")
    
    # First clear any existing keys
    echo "🔄 Clearing existing keys from agent..."
    ssh-add -D > /dev/null
    
    # Load the selected key
    echo "🔑 Activating key: $selected_key_name"
    if ssh-add "$selected_key" 2>/dev/null; then
      echo "✅ Key activated successfully"
      # Set global variables to use later
      ACTIVE_KEY_PATH="$selected_key"
      ACTIVE_KEY_NAME="$selected_key_name"
      
      # Verify only one key is active
      echo ""
      echo "Verifying key activation..."
      verify_single_key "$selected_key"
      
      return 0  # Success
    else
      echo "⚠️ Key requires passphrase:"
      if ssh-add "$selected_key"; then
        echo "✅ Key activated successfully"
        # Set global variables to use later
        ACTIVE_KEY_PATH="$selected_key"
        ACTIVE_KEY_NAME="$selected_key_name"
        
        # Verify only one key is active
        echo ""
        echo "Verifying key activation..."
        verify_single_key "$selected_key"
        
        return 0  # Success
      else
        echo "❌ Failed to activate key"
        echo "   Please select a different key"
        return 1  # Failed - try again
      fi
    fi
  elif [[ "$key_choice" =~ ^[Cc]$ ]]; then
    # Clear all keys and restart the selection process
    echo "🔄 Clearing all keys from agent..."
    ssh-add -D > /dev/null
    echo "✅ All keys cleared"
    echo ""
    echo "Press ENTER to select a new key..."
    read
    return 1  # Try again - loop back
  else
    # Keep current key (default)
    if [ -n "$current_key_fingerprint" ]; then
      echo "🔄 Keeping current key: $current_key_name"
      debug_log "Key selected: current key ($current_key_name)"
      
      # Find the key path for later use
      local current_key_path=""
      for key in "${ssh_keys[@]}"; do
        key_name=$(basename "$key")
        if [[ "$key_name" == *"$current_key_name"* ]]; then
          current_key_path="$key"
          break
        fi
      done
      
      # Set global variables to use later
      ACTIVE_KEY_PATH="$current_key_path"
      ACTIVE_KEY_NAME="$current_key_name"
      
      # Verify only one key is active
      echo ""
      echo "Verifying key activation..."
      verify_single_key "$current_key_path"
      
      return 0  # Success
    else
      echo "⚠️ No key currently active - please select one"
      debug_log "No active key found, requiring selection"
      
      # Force the user to select a key since none is active
      echo ""
      echo "👉 Please select a key number (1-${#ssh_keys[@]}):"
      echo -n "Enter key number: "
      read forced_key_num
      
      if [[ "$forced_key_num" =~ ^[0-9]+$ ]] && [ "$forced_key_num" -ge 1 ] && [ "$forced_key_num" -le "${#ssh_keys[@]}" ]; then
        local selected_key="${ssh_keys[$((forced_key_num-1))]}"
        local selected_key_name=$(basename "$selected_key")
        
        # Always make sure to clear existing keys first
        echo "🔄 Clearing any existing keys from agent..."
        ssh-add -D > /dev/null
        
        echo "🔑 Activating key: $selected_key_name"
        debug_log "Activating forced key selection: $selected_key_name"
        
        # Load the selected key
        if ssh-add "$selected_key" 2>/dev/null; then
          echo "✅ Key activated successfully"
          # Set global variables to use later
          ACTIVE_KEY_PATH="$selected_key"
          ACTIVE_KEY_NAME="$selected_key_name"
          
          # Verify only one key is active
          echo ""
          echo "Verifying key activation..."
          # Double check key verification
          if ! verify_single_key "$selected_key"; then
            echo "⚠️ Verification failed, attempting one more time..."
            ssh-add -D > /dev/null
            sleep 1
            ssh-add "$selected_key" 2>/dev/null || ssh-add "$selected_key"
          fi
          
          return 0  # Success
        else
          echo "⚠️ Key requires passphrase:"
          if ssh-add "$selected_key"; then
            echo "✅ Key activated successfully"
            # Set global variables to use later
            ACTIVE_KEY_PATH="$selected_key"
            ACTIVE_KEY_NAME="$selected_key_name"
            
            # Verify only one key is active
            echo ""
            echo "Verifying key activation..."
            verify_single_key "$selected_key"
            
            return 0  # Success  
          else
            echo "❌ Failed to activate key"
            debug_log "Failed to activate forced key selection"
            return 1  # Try again
          fi
        fi
      else
        echo "❌ Invalid key number"
        debug_log "Invalid forced key selection: $forced_key_num" 
        return 1  # Try again
      fi
    fi
  fi
}

################################
# MAIN SCRIPT EXECUTION
################################

clear
echo "┌───────────────────────────────────────────┐"
echo "│     🔐 GIT SSH AUTHENTICATION SETUP       │"
echo "└───────────────────────────────────────────┘"
echo ""

#######################################
# SECTION 1: GIT IDENTITY CONFIGURATION
#######################################
echo "STEP 1: Checking Git identity..."

if [ -z "$(git config --global user.name)" ] || [ -z "$(git config --global user.email)" ]; then
  echo "❌ Git identity not configured in container"
  echo ""
  echo "Options:"
  echo "  Y - Configure Git identity now"
  echo "  N - Skip (not recommended)"
  read -p "Configure Git identity? [Y/n]: " setup_git
  
  if [[ ! "$setup_git" =~ ^[Nn]$ ]]; then
    read -p "Enter your Git user name: " git_username
    read -p "Enter your Git email address: " git_email
    git config --global user.name "$git_username"
    git config --global user.email "$git_email"
    echo "✅ Git identity configured"
  else
    echo "⚠️ Skipping Git identity configuration"
  fi
else
  echo "✅ Git identity detected: $(git config --global user.name) <$(git config --global user.email)>"
fi

echo ""

#######################################
# SECTION 2: SSH CONFIG FIXES
#######################################
echo "STEP 2: Checking SSH configuration..."

# Fix SSH config issues
SSH_CONFIG_FIXED=false

# Fix UseKeychain option (not supported in Linux containers)
if [ -f ~/.ssh/config ] && grep -q "UseKeychain" ~/.ssh/config; then
  echo "🔧 Fixing SSH config: removing macOS-specific UseKeychain option..."
  # Create a backup
  cp ~/.ssh/config ~/.ssh/config.bak
  # Remove UseKeychain lines
  sed -i '/UseKeychain/d' ~/.ssh/config
  SSH_CONFIG_FIXED=true
fi

# Fix macOS paths in SSH config
if [ -f ~/.ssh/config ] && grep -q "/Users/" ~/.ssh/config; then
  echo "🔧 Fixing SSH config: adjusting macOS paths to container paths..."
  # Replace macOS paths with container paths
  sed -i 's|/Users/[^/]*/\.ssh/|~/.ssh/|g' ~/.ssh/config
  SSH_CONFIG_FIXED=true
fi

if [ "$SSH_CONFIG_FIXED" = true ]; then
  echo "✅ SSH config fixed (backup saved at ~/.ssh/config.bak)"
else
  echo "✅ SSH config looks good"
fi

# Start SSH agent if not running
if ! ssh-add -l &>/dev/null; then
  echo "🔄 Starting SSH agent..."
  eval "$(ssh-agent -s)"
else
  echo "✅ SSH agent already running"
fi

echo ""

#######################################
# SECTION 3: SSH KEY MANAGEMENT
#######################################
# Global variables to store key information
ACTIVE_KEY_PATH=""
ACTIVE_KEY_NAME=""

# Keep trying until we get a successful key setup
while true; do
  manage_ssh_keys
  result=$?
  
  if [ $result -eq 0 ]; then
    # Success - we have an active key
    break
  elif [ $result -eq 2 ]; then
    # Fatal error
    echo "Exiting due to fatal error"
    exit 1
  fi
  # If result is 1, loop will continue
done

# Show final key selection
echo ""
echo "📋 Current active SSH key:"
updated_keys=$(ssh-add -l 2>/dev/null)
if [ $? -eq 0 ] && [ -n "$updated_keys" ]; then
  echo "$updated_keys" | sed 's/^/   /'
  
  # Verify ACTIVE_KEY_NAME is set
  if [ -z "$ACTIVE_KEY_NAME" ]; then
    echo "⚠️ Active key name not captured, using first key"
    ACTIVE_KEY_NAME=$(echo "$updated_keys" | head -1 | awk '{print $3}')
  fi
else
  echo "   Error: No SSH key active"
  echo "❌ No SSH key active - cannot continue"
  exit 1
fi

echo ""

#######################################
# SECTION 4: GITHUB SSH CONFIGURATION
#######################################
echo "STEP 4: Configuring GitHub SSH access..."

# GitHub SSH configuration
if [ -n "$ACTIVE_KEY_NAME" ]; then
  echo "Performing final verification before GitHub configuration..."
  
  # Force clearing all keys and readding only the selected key
  echo "🔄 Final check: ensuring only the selected key is active..."
  ssh-add -D > /dev/null
  if [ -n "$ACTIVE_KEY_PATH" ]; then
    echo "🔑 Activating ONLY: $ACTIVE_KEY_NAME"
    ssh-add "$ACTIVE_KEY_PATH" &>/dev/null || ssh-add "$ACTIVE_KEY_PATH"
    
    # Display currently active keys
    echo "📋 Verifying current active SSH keys:"
    ssh-add -l | sed 's/^/   /'
    
    # Count keys to verify
    num_active_keys=$(ssh-add -l 2>/dev/null | grep -E "SHA256|MD5" | wc -l)
    if [ "$num_active_keys" -ne 1 ]; then
      echo "⚠️ Warning: Found $num_active_keys active keys instead of exactly 1"
      echo "   This may cause issues with GitHub SSH authentication"
    else
      echo "✅ Verification successful: exactly 1 key active"
    fi
  fi
  
  echo "✅ Using active SSH key for GitHub: $ACTIVE_KEY_NAME"
  
  # Create GitHub-specific SSH config entry with current key
  mkdir -p ~/.ssh
  cat >> ~/.ssh/config << EOF

# Added by setup-git-ssh.sh
Host github.com
  HostName github.com
  User git
  IdentitiesOnly yes
  IdentityAgent SSH_AUTH_SOCK
EOF
  echo "✅ GitHub SSH config updated to use current key"
else
  echo "❌ No SSH key currently active"
  echo "   Please run this script again and activate a key"
  exit 1
fi

#######################################
# SECTION 5: TESTING & VERIFICATION
#######################################
echo "STEP 5: Testing & verification..."

# Test SSH connection to GitHub
echo "🔄 Testing SSH connection to GitHub..."
if ssh -T git@github.com -o BatchMode=yes -o StrictHostKeyChecking=accept-new 2>&1 | grep -q "successfully authenticated"; then
  echo "✅ SSH connection to GitHub successful!"
else
  echo "⚠️ SSH connection test returned unexpected result"
  echo ""
  echo "📋 Output from SSH test:"
  ssh -T git@github.com -o StrictHostKeyChecking=accept-new
  echo ""
  echo "⚠️ If connection failed, try running with DEBUG=1 for verbose output:"
  echo "   DEBUG=1 .devcontainer/setup-git-ssh.sh"
fi

# Configure Git to prefer SSH
echo ""
echo "🔄 Configuring Git to use SSH for GitHub repositories..."
git config --global url."git@github.com:".insteadOf "https://github.com/"
echo "✅ Git configured to use SSH for GitHub URLs"

echo ""
echo "┌───────────────────────────────────────────┐"
echo "│     🎉 GIT SSH SETUP COMPLETE!            │"
echo "└───────────────────────────────────────────┘"
echo ""
echo "You can now use Git with SSH authentication:"
echo "  $ git clone git@github.com:username/repo.git"
echo "  $ git push origin main"
echo ""
echo "For troubleshooting, run: DEBUG=1 .devcontainer/setup-git-ssh.sh"
echo "" 