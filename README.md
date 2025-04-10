# Sonne - A simple static site generator for minimally footprinted blogs and showcases

"I want to host a blog but don't want to use so much compute to have it dynamically hosted!"
"I'm happy with static site hosting but its so much effort to make new blog posts!"
"I'm using another static site generator but its so complicated to set up and-"
Chill out, hier kommt die Sonne.


I've created Sonne to generate the static site that is powered by my home solar server. I also wanted a blog. Sonne allows for that, as well as the setting of variables inline in your documents, to be replaced by variables updated on run by Sonne.

Let's go over some features and how to use them:


### Setup
To start the setup where your base webpages are stored in 'www', for example, simply 
`cd www` and run `sonne`.
If Sonne hasn't already done configuration in that folder, it will enter setup mode, asking if you'd like to use defaults (recommended) or custom settings, which will ask questions about where you're storing things and what features you'd like to use. These configurations are stored as sonne.config

### Variables 
To include a Sonne variable inline in ANY of your documents, like your solar setup's battery percentage, Sonne looks for the following a simple format `{+}{battery_level}`. This can be escaped with a backslash \{+}{variable_name}. 

Just to get your imagination going, these variables can be entire HTML elements too, just imagine you're editing the innerHTML in JS. 

These variables are will be stored in the directory where Sonne was run from, your webpage directory. To populate these, Sonne will run any python scripts that are placed in the /sonne_sources directory. From these, simply `import sonne_source` and return a value to Sonne by calling `sonne_source.return(variable_name, data)` which will write or overwrite the stored variable_name with the provided data. Easy enough, yeah?

### Blogging
By default, Sonne will crawl your /blog directory for .md files and write pages from there. Sonne variables work like expected, but for blogs you're also able to take advantage of local variables, called Mond variables. Each blog post will have its own Mond variables populated naturally. Simply place them inline using {-}{date_created}. Some Mond variables include:
- date_created
- date_edited
- author
- title
- subtitle
- category

### Images
Images placed by Sonne are, by default, dithered to save traffic, load times, and page size for end-users. This can be disabled in setup or through the configuration file by the boolean `dither-images` flag.

Image elements will be automagically replaced by divs which contain this image and a button to request the original, unadulterated image.

### More
For now, that's all I'll plan to implement. This is already quite an undertaking for what was supposed to be an easy app.

### Licensing
I believe in the effective applications of free and open software, so long as they aren't exploited for financial gain. Manipulating, forking, sharing, and any other modifications are more than welcome for non-commercial uses provided there is proper credit given. Commercial use of this project in any form, unsanctioned by me, is strictly forbidden.













