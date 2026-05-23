# Wax | Wane Product Automation Pipeline: n8n Setup Guide

This guide explains how to import and activate the single-source-of-truth product automation pipeline in your local n8n instance.

## What This Automation Does

When you publish a new product in Shopify (even with just a title and images), this workflow automatically:
1. **Extracts** the product details and variants.
2. **Enriches** the content using AI (GPT-4o) in Samantha's voice, generating:
   - Shopify SEO Title & Meta Description
   - Full HTML Description (with Gemini grade callouts and natural variation disclaimers)
   - Care Instructions
   - Amazon Title & Bullets (formatted with ALL CAPS labels)
   - Walmart Short Description
   - Social Media Captions (TikTok, Instagram, Facebook) with validated URLs
   - Blog Post Title & Intro
3. **Writes back** the enriched content to Shopify (Description, Tags, and Metafields).
4. **Pushes** the updated content to Veeqo, which automatically syncs to your connected sales channels (Walmart, TikTok, Amazon, Etsy).
5. **Waits 24 hours**, then generates and publishes a full educational blog post about the product on your Shopify store.
6. **Prepares** social media posts with the blog link and posts to your Facebook Page.
7. **Logs** the completed run.

## Step 1: Import the Workflow

1. Open your local n8n instance (usually `http://localhost:5678`).
2. Click **Workflows** in the left sidebar, then click **Add Workflow**.
3. Click the **Options** menu (three dots) in the top right corner and select **Import from File**.
4. Select the `wax_wane_product_automation.json` file provided.

## Step 2: Configure Credentials

You need to set up three credentials in n8n for this workflow to function:

### 1. Shopify Admin API
1. In n8n, go to **Credentials** -> **Add Credential** -> **Header Auth**.
2. Name it `Shopify Admin API`.
3. Set **Name** to `X-Shopify-Access-Token`.
4. Set **Value** to your Shopify Admin API token (`shpat_...`).

### 2. OpenAI API
1. In n8n, go to **Credentials** -> **Add Credential** -> **OpenAI API**.
2. Enter your OpenAI API key.

### 3. Veeqo API
1. In n8n, go to **Credentials** -> **Add Credential** -> **Header Auth**.
2. Name it `Veeqo API`.
3. Set **Name** to `x-api-key`.
4. Set **Value** to your Veeqo API token (`Vqt/...`).

## Step 3: Set Up the Shopify Webhook

1. In the n8n workflow, double-click the first node (**🛍️ Shopify: Product Published**).
2. Copy the **Test URL** (for testing) or **Production URL** (for live use).
   *Note: Since your n8n is running locally, you will need a tunneling service like ngrok or Cloudflare Tunnels to expose your local n8n webhook URL to the public internet so Shopify can reach it.*
3. Go to your Shopify Admin -> **Settings** -> **Notifications** -> **Webhooks**.
4. Click **Create webhook**.
5. Set **Event** to `Product creation`.
6. Set **Format** to `JSON`.
7. Paste the n8n webhook URL into the **URL** field.
8. Click **Save**.

## Step 4: Final Adjustments

1. **Blog ID**: Run the workflow once manually (or trigger it with a test product). Check the output of the **📚 Get Shopify Blog ID** node to find your specific blog ID. Update the URL in the **📝 Shopify: Publish Blog Post** node with this ID.
2. **Facebook Page Token**: In the **📘 Post to Facebook Page** node, replace `YOUR_FACEBOOK_PAGE_ACCESS_TOKEN` with your actual long-lived Facebook Page access token.
3. **Activate**: Toggle the workflow switch in the top right corner of n8n to **Active**.

## Future Considerations & Upgrades

*   **Local Hosting vs. Cloud**: Currently, your n8n runs locally on your MacBook. This means your MacBook must be awake and connected to the internet to receive Shopify webhooks and process the 24-hour wait node. For a truly "set and forget" production environment, consider migrating your n8n instance to a cloud VPS (like DigitalOcean or Hetzner) or using n8n Cloud. This ensures 24/7 uptime without relying on your personal hardware.
*   **Error Handling**: As you scale, you might want to add an Error Trigger node to catch any API failures (e.g., OpenAI rate limits or Shopify timeouts) and send an alert to your email or Slack.
*   **Image Processing**: Future iterations could integrate the Canva MCP to automatically resize and watermark product images for different channels before pushing them via Veeqo.
