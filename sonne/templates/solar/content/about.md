---
title: About Solar Template
template: page.html
---

# About the Solar Template

The Solar template is a specialized theme for the Sonne static site generator designed with energy efficiency as its primary goal. This template demonstrates how websites can be designed to minimize energy consumption while still providing a great user experience.

## Technical Specifications

- **File Size**: Total template size < 50KB
- **Font**: System fonts only to avoid additional downloads
- **Images**: Dithering for reduced file size
- **JavaScript**: Minimal JS for essential functionality only
- **CSS**: Critical CSS inlined, remainder deferred
- **Colors**: Dark mode default to reduce OLED screen power usage
- **Animation**: Reduced motion option for energy savings

## Environmental Impact

Websites contribute to carbon emissions in several ways:

1. **Server Energy**: Power required to serve web content
2. **Network Transfer**: Energy used to transfer data across the internet
3. **Client Rendering**: Processing power used by the user's device
4. **Device Charging**: Battery impact from web browsing

By optimizing in all these areas, the Solar template significantly reduces the carbon footprint of websites that use it.

## Features and Performance

Despite its focus on minimalism and efficiency, the Solar template includes all essential features:

- Full blog support with tags and categories
- Portfolio/project showcase
- Responsive design for all devices
- Weather API integration with 3-day forecast
- Device battery status monitoring
- Theme switching with dark/light modes

## Battery Status Simulation

The template includes a battery status simulation that demonstrates how a solar-powered server might operate. During daylight hours, the battery shows charging status; at night, it displays discharging.

In a real-world implementation, this could be connected to actual battery and solar panel data.

## Weather Integration

Weather data for Long Beach, CA is displayed to demonstrate API integration. The weather service is designed to:

1. Minimize API calls by caching data
2. Use text-based weather icons instead of images
3. Fetch only essential data to reduce transfer size

## Usage Guidelines

This template is ideal for:

- Solar-powered websites and servers
- Low-bandwidth environments
- Mobile-first content
- Environmental organizations
- Demonstrating sustainable web design

## Credits

The Solar template was created by the Sonne development team. Weather data is provided by OpenWeatherMap's free API. All images used in the template are open-source and optimized for minimal file size.

## Get Started

To use this template for your own site, run:

```bash
sonne new -p my-site -t solar
```

Then customize the content in the `content` directory to make it your own!