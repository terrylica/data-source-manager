#!/bin/bash

# Script to switch the default GitHub SSH key

# Display available identities
echo "Available SSH identities:"
keys=()
i=0
while IFS= read -r line; do
  keys+=("$line")
  email=""
  if [[ -f "${line}.pub" ]]; then
    email=$(cat "${line}.pub" | awk '{print $3}')
  fi
  echo "   $((i+1))) $(basename "$line") ${email:+($email)}"
  i=$((i+1))
done < <(find ~/.ssh -name "id_*" | grep -v "\.pub$" | grep -v "\.bak$" | sort)

# Get user choice
echo ""
echo "Which identity would you like to set as default for github.com?"
read -p "Enter a number (1-${#keys[@]}): " choice

# Validate choice
if [[ ! "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#keys[@]}" ]; then
  echo "Invalid selection: $choice"
  exit 1
fi

selected_key="${keys[$((choice-1))]}"
key_name=$(basename "$selected_key")
echo "Selected: $key_name"

# Get email from public key
email=""
if [[ -f "${selected_key}.pub" ]]; then
  email=$(cat "${selected_key}.pub" | awk '{print $3}')
fi

# Backup original config
cp ~/.ssh/config ~/.ssh/config.bak.$(date +%Y%m%d%H%M%S)

# Simple approach: Search and replace existing identity file for github.com
if grep -q "^Host github.com$" ~/.ssh/config; then
  # Update the existing IdentityFile line
  sed -i.tmp -E "/^Host github.com$/,/^Host |^$/ s|(IdentityFile ).+$|\1${selected_key}|" ~/.ssh/config
  rm -f ~/.ssh/config.tmp
  echo "SSH config updated: Changed IdentityFile to $key_name"
else
  # Add new github.com entry at the end of the file
  cat >> ~/.ssh/config << EOF

# Default GitHub configuration
Host github.com
    HostName github.com
    User git
    IdentityFile ${selected_key}
    PreferredAuthentications publickey
    IdentitiesOnly yes
EOF
  echo "SSH config updated: Added new github.com entry with $key_name"
fi

# Test the connection
echo ""
echo "Testing connection to GitHub..."
output=$(ssh -T git@github.com 2>&1)
if [[ "$output" == *"successfully authenticated"* ]]; then
  echo "✅ GitHub authentication successful!"
  echo "   $output"
else
  echo "❌ GitHub authentication failed."
  echo "   $output"
fi

# Optionally update git config
if [ -n "$email" ]; then
  echo ""
  read -p "Would you like to update your Git identity to match ($email)? [y/N]: " update_git
  if [[ "$update_git" =~ ^[Yy]$ ]]; then
    # Extract name from email
    name=$(echo "$email" | cut -d@ -f1 | sed 's/\./\ /g' | sed 's/\<./\U&/g')
    read -p "Enter your name [$name]: " custom_name
    name=${custom_name:-$name}
    
    git config --global user.name "$name"
    git config --global user.email "$email"
    echo "✅ Git identity updated to: $name <$email>"
  fi
fi

echo ""
echo "All done! You can now use git@github.com with your selected identity." 