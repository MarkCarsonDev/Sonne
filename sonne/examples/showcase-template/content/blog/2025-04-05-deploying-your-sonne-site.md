---
title: Deploying Your Sonne Site
date: 2025-04-05
author: Miguel Rodriguez
tags:
  - deployment
  - hosting
  - production
categories:
  - guides
featured: false
cover_img: /assets/images/deployment.jpg
description: A comprehensive guide to deploying your Sonne static site to various hosting platforms.
---

# Deploying Your Sonne Site

After building your site with Sonne, the next step is to deploy it to a web server where it can be accessed by your audience. Since Sonne generates a completely static site, you have many flexible, cost-effective hosting options. This guide covers various deployment methods, from simple to advanced.

## Preparing for Deployment

Before deploying your site, there are a few important steps to prepare:

### 1. Configure Production Settings

Update your `sonne.yaml` configuration file with production settings:

```yaml
site:
  title: My Awesome Site
  base_url: https://www.example.com  # Set this to your actual domain
  description: My production-ready site
```

The `base_url` setting is particularly important as it affects absolute URLs in your site, such as canonical links, social media sharing metadata, and the sitemap.

### 2. Build Your Site for Production

Run a clean production build:

```bash
sonne build --clean
```

The `--clean` flag ensures that any old files from previous builds are removed, giving you a fresh output.

### 3. Test Your Build Locally

Before deploying, test your production build locally:

```bash
sonne serve --path output
```

This serves the built site from the `output` directory, allowing you to verify everything works as expected.

### 4. Optimize for Production

Consider additional optimization steps:

- **Minify HTML/CSS/JS**: If not already handled by your template
- **Optimize images**: Double-check that images are properly optimized
- **Check for broken links**: Use a tool like [broken-link-checker](https://github.com/stevenvachon/broken-link-checker)
- **Validate HTML**: Use the [W3C Validator](https://validator.w3.org/)

## Deployment Options

### Option 1: GitHub Pages

GitHub Pages is one of the simplest hosting options for static sites. It's free, secure, and integrates well with GitHub repositories.

#### Setup Steps:

1. **Create a GitHub repository** for your site

2. **Create a `.github/workflows/deploy.yml` file** to automate deployment:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches:
      - main  # or your default branch

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install sonne
          
      - name: Build site
        run: |
          sonne build --clean
      
      - name: Deploy to GitHub Pages
        uses: JamesIves/github-pages-deploy-action@v4
        with:
          folder: output  # The folder the action should deploy
```

3. **Push your code** to GitHub:

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

4. **Configure GitHub Pages** in your repository settings to deploy from the GitHub Actions branch.

5. **Add a custom domain** (optional):
   - In your repository settings, add your custom domain
   - Create a `CNAME` file in your `static` directory with your domain

#### Advantages:
- Free hosting
- Built-in HTTPS
- Easy integration with GitHub workflow
- Global CDN

#### Limitations:
- Limited to GitHub's capabilities
- No server-side functionality

### Option 2: Netlify

Netlify offers a powerful platform for deploying static sites with additional features like forms, serverless functions, and split testing.

#### Setup Steps:

1. **Create a `netlify.toml` file** in your project root:

```toml
[build]
  command = "pip install sonne && sonne build"
  publish = "output"

[build.environment]
  PYTHON_VERSION = "3.10"

[[redirects]]
  from = "/*"
  to = "/404.html"
  status = 404
```

2. **Sign up for Netlify** and connect your GitHub repository

3. **Configure the build settings**:
   - Build command: `pip install sonne && sonne build`
   - Publish directory: `output`

4. **Deploy your site**:
   - Netlify will automatically build and deploy your site when you push to your repository

5. **Set up a custom domain** (optional):
   - In the Netlify dashboard, go to Site settings > Domain management
   - Add your custom domain and follow the instructions

#### Advantages:
- Free tier is generous
- Continuous deployment
- Easy rollbacks
- Built-in form handling
- Serverless functions
- Edge computing capabilities
- Global CDN

#### Limitations:
- Some advanced features require paid plans

### Option 3: Vercel

Vercel is another excellent platform for static sites, with a focus on performance and developer experience.

#### Setup Steps:

1. **Create a `vercel.json` file** in your project root:

```json
{
  "buildCommand": "pip install sonne && sonne build",
  "outputDirectory": "output",
  "installCommand": "pip install -r requirements.txt"
}
```

2. **Create a `requirements.txt` file**:

```
sonne>=0.2.0
```

3. **Sign up for Vercel** and connect your GitHub repository

4. **Configure the build settings**:
   - Framework Preset: Other
   - Build Command: `pip install sonne && sonne build`
   - Output Directory: `output`

5. **Deploy your site**:
   - Vercel will automatically build and deploy your site when you push to your repository

#### Advantages:
- Free tier is generous
- Excellent performance
- Preview deployments for every PR
- Serverless functions
- Edge computing capabilities
- Global CDN

#### Limitations:
- Some advanced features require paid plans

### Option 4: AWS S3 + CloudFront

For more control or enterprise requirements, AWS offers a robust solution with S3 for storage and CloudFront for content delivery.

#### Setup Steps:

1. **Create an S3 Bucket**:
   - Sign in to the AWS Management Console
   - Navigate to S3 and create a new bucket
   - Enable "Static website hosting" in the bucket properties

2. **Set up a bucket policy** to allow public read access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::your-bucket-name/*"
    }
  ]
}
```

3. **Create a CloudFront distribution**:
   - Navigate to CloudFront and create a new distribution
   - Set the origin to your S3 bucket's website endpoint
   - Configure cache behavior and other settings as needed

4. **Create a deployment script** (example using AWS CLI):

```bash
#!/bin/bash

# Build the site
sonne build --clean

# Sync the output directory with S3
aws s3 sync output/ s3://your-bucket-name/ --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id YOUR_DISTRIBUTION_ID --paths "/*"
```

5. **Set up a custom domain** (optional):
   - In Route 53, create a new record set
   - Point it to your CloudFront distribution

#### Advantages:
- Highly scalable
- Complete control over configuration
- Advanced caching options
- Pay only for what you use
- Global CDN

#### Limitations:
- More complex setup
- Costs can add up for high-traffic sites
- Requires AWS knowledge

### Option 5: Traditional Web Hosting

If you prefer traditional web hosting or already have a hosting plan, you can deploy your Sonne site using FTP or SFTP.

#### Setup Steps:

1. **Build your site**:

```bash
sonne build --clean
```

2. **Upload the contents of the `output` directory** to your web host:
   - Using an FTP client like FileZilla or Cyberduck
   - Upload to the public directory (often `public_html` or `www`)

3. **Configure your web server** (if you have access):
   - For Apache, create or edit `.htaccess` for clean URLs:

```apache
# Enable URL rewriting
RewriteEngine On

# Remove .html extension
RewriteCond %{REQUEST_FILENAME} !-d
RewriteCond %{REQUEST_FILENAME}\.html -f
RewriteRule ^(.*)$ $1.html

# Custom 404 page
ErrorDocument 404 /404.html
```

   - For Nginx, edit your server configuration:

```nginx
server {
    listen 80;
    server_name example.com www.example.com;
    root /var/www/html;
    index index.html;

    # Remove .html extension
    location / {
        try_files $uri $uri.html $uri/ =404;
    }
    
    # Custom 404 page
    error_page 404 /404.html;
}
```

#### Advantages:
- Works with existing hosting plans
- Often includes email hosting
- Complete control over server (if you have VPS or dedicated hosting)

#### Limitations:
- Usually more expensive
- Manual deployment process
- May not include CDN

## Advanced Deployment Strategies

### Automated Deployment with GitHub Actions

For any hosting provider, you can set up automated deployments using GitHub Actions:

1. **Create a `.github/workflows/deploy.yml` file**:

```yaml
name: Deploy Website

on:
  push:
    branches:
      - main

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install sonne pillow requests

      - name: Build site
        run: sonne build --clean
        
      # Example deployment step for S3
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Deploy to S3
        run: aws s3 sync output/ s3://your-bucket-name/ --delete

      - name: Invalidate CloudFront
        run: aws cloudfront create-invalidation --distribution-id ${{ secrets.CLOUDFRONT_DISTRIBUTION_ID }} --paths "/*"
```

2. **Set up repository secrets** for any sensitive credentials

3. **Push to your main branch** to trigger the deployment

### Staging Environments

For larger sites, it's often useful to have separate staging and production environments:

1. **Create branch-specific configurations**:

```yaml
# config.dev.yaml
site:
  title: My Site (Dev)
  base_url: https://dev.example.com

# config.prod.yaml
site:
  title: My Site
  base_url: https://www.example.com
```

2. **Set up branch-specific workflows**:

```yaml
name: Deploy

on:
  push:
    branches:
      - main
      - develop

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      # ... (setup steps) ...
      
      - name: Set configuration based on branch
        run: |
          if [[ $GITHUB_REF == 'refs/heads/main' ]]; then
            cp config.prod.yaml sonne.yaml
            export DEPLOY_ENVIRONMENT=production
          else
            cp config.dev.yaml sonne.yaml
            export DEPLOY_ENVIRONMENT=staging
          fi
          echo "DEPLOY_ENVIRONMENT=$DEPLOY_ENVIRONMENT" >> $GITHUB_ENV
      
      # ... (build steps) ...
      
      - name: Deploy to appropriate environment
        run: |
          if [[ $DEPLOY_ENVIRONMENT == 'production' ]]; then
            # Deploy to production
          else
            # Deploy to staging
          fi
```

### Performance Optimization

To ensure your site loads quickly after deployment:

1. **Set up proper caching headers**:

For S3/CloudFront:
```bash
aws s3 sync output/ s3://your-bucket-name/ \
  --delete \
  --cache-control "max-age=31536000" \
  --exclude "*.html" \
  --exclude "*.xml" \
  --exclude "*.txt"

aws s3 sync output/ s3://your-bucket-name/ \
  --delete \
  --cache-control "max-age=0, must-revalidate" \
  --include "*.html" \
  --include "*.xml" \
  --include "*.txt"
```

For Netlify, in `netlify.toml`:
```toml
[[headers]]
  for = "/*"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"

[[headers]]
  for = "/*.css"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[headers]]
  for = "/*.js"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[headers]]
  for = "/images/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

2. **Implement content hashing** for assets:

If your template supports it, implement content hashing for CSS and JS files to enable long-term caching.

3. **Configure a CDN** for global distribution

## Domain Configuration and HTTPS

### Custom Domain Setup

1. **Purchase a domain** from a registrar like Namecheap, GoDaddy, or Google Domains

2. **Configure DNS settings**:
   - For GitHub Pages, create an `A` record pointing to GitHub's IP addresses
   - For Netlify/Vercel, create a `CNAME` record pointing to your deployment URL
   - For AWS, create an `A` record pointing to your CloudFront distribution

3. **Set up www subdomain** (recommended):
   - Create a `CNAME` record for `www` pointing to your domain
   - Configure your hosting provider to redirect from `www` to non-www (or vice versa)

### HTTPS Configuration

Most modern hosting providers set up HTTPS automatically:

- **GitHub Pages**: Automatic with Enforce HTTPS option
- **Netlify/Vercel**: Automatic HTTPS with Let's Encrypt
- **AWS**: Use ACM (AWS Certificate Manager) with CloudFront

For traditional hosting:

1. **Obtain an SSL certificate**:
   - Let's Encrypt (free)
   - Commercial SSL certificate

2. **Install the certificate** on your web server

3. **Configure redirects** from HTTP to HTTPS:

For Apache:
```apache
RewriteEngine On
RewriteCond %{HTTPS} off
RewriteRule (.*) https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]
```

For Nginx:
```nginx
server {
    listen 80;
    server_name example.com www.example.com;
    return 301 https://$host$request_uri;
}
```

## Monitoring and Maintenance

After deployment, it's important to monitor your site and maintain it:

### Analytics and Monitoring

1. **Set up analytics**:
   - Google Analytics
   - Plausible Analytics (privacy-focused)
   - Fathom Analytics (privacy-focused)

2. **Implement uptime monitoring**:
   - UptimeRobot (free tier available)
   - Pingdom
   - StatusCake

3. **Set up error tracking**:
   - Sentry
   - LogRocket

### Ongoing Maintenance

1. **Regular content updates**:
   - Add new blog posts
   - Update existing content

2. **Technical maintenance**:
   - Update Sonne and dependencies
   - Refresh SSL certificates (if not automatic)
   - Check for broken links
   - Monitor performance metrics

3. **Backup your site**:
   - Regular backups of your source files
   - Consider versioning with Git

## Troubleshooting Common Deployment Issues

### 404 Errors for Pages

**Problem**: Some pages return 404 errors after deployment.

**Solutions**:
- Check that all pages were built correctly in your output directory
- Verify your URL structure matches what's expected by your hosting provider
- Check for case sensitivity issues in file paths
- Configure proper rewrites for clean URLs

### CSS and JavaScript Not Loading

**Problem**: Styles or scripts are missing on the deployed site.

**Solutions**:
- Check that all files were uploaded/deployed
- Verify the paths in your HTML (absolute vs. relative)
- Check browser console for errors
- Verify that MIME types are set correctly on your server

### Images Not Displaying

**Problem**: Images show as broken on the deployed site.

**Solutions**:
- Check that images were uploaded/deployed
- Verify image paths in your HTML
- Check for case sensitivity in file names
- Ensure image formats are web-compatible
- Verify that large images aren't being blocked by server configurations

### Slow Loading Times

**Problem**: Site loads slowly after deployment.

**Solutions**:
- Check image sizes and optimize if necessary
- Implement browser caching
- Set up a CDN if not already using one
- Minify CSS and JavaScript
- Use lazy loading for images and videos

## Conclusion

Deploying a Sonne site is straightforward due to its static nature, giving you numerous hosting options. Whether you prefer the simplicity of GitHub Pages, the features of Netlify/Vercel, or the control of AWS, your Sonne site can be deployed efficiently and cost-effectively.

Remember that a well-planned deployment strategy should consider not just the initial launch, but also ongoing maintenance, performance optimization, and monitoring. By following the guidelines in this article, you'll ensure your Sonne site remains fast, secure, and accessible to your audience.

## Further Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Netlify Documentation](https://docs.netlify.com/)
- [Vercel Documentation](https://vercel.com/docs)
- [AWS S3 Static Website Hosting](https://docs.aws.amazon.com/AmazonS3/latest/userguide/WebsiteHosting.html)
- [CloudFront Documentation](https://docs.aws.amazon.com/cloudfront/index.html)
- [Let's Encrypt](https://letsencrypt.org/) for free SSL certificates
- [Google PageSpeed Insights](https://pagespeed.web.dev/) for performance testing