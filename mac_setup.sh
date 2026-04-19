#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# Wax | Wane — One-Time Mac Setup
# Run this ONCE in terminal. After that, tokens load automatically.
# ─────────────────────────────────────────────────────────────────
# Usage: bash ~/mac_setup.sh

echo ""
echo "Setting up Wax | Wane token environment..."

# Write tokens to ~/.waxwane_env
cat > ~/.waxwane_env << 'ENVEOF'
# Wax | Wane Social Media Tokens
# Last updated: Apr 2026
# Instagram: @waxandwane.store (ID: 17841458399612807)
# Facebook: Niche Wellness Page (ID: 203171376205580)
# Token: Meta Conversions API System User — never expires

export IG_TOKEN="EAASgzu1LdvABRJPUrCLFfT6SBuUyeJu3QV2PQexpOE7Xfvlo0rvdbIQVzdZCEp7eqDo7vxegIn8y52cnLYCntTHKE3mlx4fhoECAyp0SanD0Ju9XCdRFEBzCKdSUE0nB5SHuAndO6dNJEz0VVjTvvscTVTaffV8twSu1gLBk0ZCt0DYtkG0gSE1sZBcJQZDZD"
export IG_USER_ID="17841458399612807"
export FB_PAGE_ID="203171376205580"
export FB_PAGE_TOKEN="EAASgzu1LdvABRFou790AZAdQdTlernJZACPM0dRcDgP12LiNhHFND1ztu01Hr8CnkW4sH9zvivJqRi5rQryscOio5KFXO2xRZCPYonnZBFVfO4lJZB9LUq8NdGjtT9dHHDTv8woZAEYUFoaDz6FmBSRlKdfP20HZBsZBEq1MH4w4uWIMJTRzKZB1fso3ZB7xOKZCFNzBq502jMZD"
ENVEOF

echo "  ✓ Token file created at ~/.waxwane_env"

# Add to ~/.zshrc if not already there
if ! grep -q "waxwane_env" ~/.zshrc 2>/dev/null; then
    echo "" >> ~/.zshrc
    echo "# Wax | Wane tokens (auto-load)" >> ~/.zshrc
    echo "[ -f ~/.waxwane_env ] && source ~/.waxwane_env" >> ~/.zshrc
    echo "  ✓ Added to ~/.zshrc — tokens will load automatically in every new terminal"
else
    echo "  ✓ ~/.zshrc already configured"
fi

# Load now for this session
source ~/.waxwane_env

echo ""
echo "Setup complete! You never need to type 'export IG_TOKEN=...' again."
echo ""
echo "To post the next item in your queue:"
echo "  python3 ~/waxwane_post.py"
echo ""
echo "To see what's pending:"
echo "  python3 ~/waxwane_post.py --preview"
echo ""
