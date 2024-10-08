# DeviantArt Post Bot

Post images, auto-magically!

## Warning

Fair warning: I do not intend on making this user-friendly. 
It is likely that this will not work for you as this is a niche implementation for my personal use.
If you want a certain feature or a current feature to work differently, fork it and make your own custom version. 
This is **not** intended to be generalized or perfect for your use case. 
There are already other projects out there that are more general, but they do not fit my use case.

## Setup

To start the setup, clone the repo to your machine.

### Setting Up The Config

If you want to set this up as your own application in DeviantArt (in case mine gets taken down), you should first follow the instructions in [info.md](./info.md)

An example configuration is provided in [example_config.json](./example_config.json). 
This should give you a general idea of how the file is laid out. 

Within `post_config` is where your configuration of different post types will go. The names of each must be unique and include the following fields:

```json 
{
  "type": "daily|rotation",
  "images_per_day": 1,
  "time": "01:01",
  "galleries": [
    "gallery1",
    "gallery2",
    "..."
  ],
  "tags": [
    "type dependent"
  ]
}
```

For daily postings, your config should look something like this:

```json 
{
  "daily_images": {
    "type": "daily",
    "directory": "path/to/images",
    "images_per_day": 1,
    "time": "01:01",
    "galleries": [
        "folderid1",
        "folderid2"
    ],
    "tags": [
        "tag1",
        "tag2"
    ]
  }
}
```

For rotation postings, your config should look something like this:

```json 
{
  "rotation_images": {
    "type": "rotation",
    "last_posted": 0,
    "directories": [
      "path/to/first/folder",
      "path/to/second/folder",
      "and/so/on"
    ],
    "images_per_day": 1,
    "time": "01:01",
    "galleries": [
        "folderid1",
        "folderid2"
    ],
    "tags": [
        "tag1",
        "tag2"
    ]
  }
}
```

Before running the application, you will **need** to rename the file to `da_config.json`. 
Otherwise, the application will not run. 

I would also recommend using absolute paths for the directories to hopefully avoid issues caused by messing up relative paths (though they are supported). 

### Obtaining Folder IDs

As this is a rather niche use case, I haven't bothered automating getting folder ids.
So, you will have to use the [console from DeviantArt](https://www.deviantart.com/developers/console/gallery/gallery_folders/f6104e0d969bbbdcf2154e4b221aa3a6) to see all of your folders.

From there, you will need the value of `folderid` of the folders you are going to try to post to. 
These are the values you will need for the `galleries` field of the post configurations. 

### Run The Application Locally

Set up a virtual environment how you prefer, or just run it if you have all requirements in your environment already. 

Then run the application:

```shell 
py main.py
```

or on POSIX compliant OSs:

```shell 
python3 main.py
```

This will open DeviantArt's OAUTH page in your default browser. 
After authenticating the application, `refresh_token` in the config will be your new token. 

I could make a script for doing this, but this is niche and I do not intend on others using this. 
Think of it as a reference for making your own niche script. 

### Running It For Real Now, Locally

Now that the configuration is settled, you can finally run everything. 
You may do this locally with the same commands from before in [Run The Application Locally](#run-the-application-locally).

### Running It For Real Now, But In Docker

```yml 
services:
  da-poster:
    image: samhaswon/da-poster:latest
    container_name: da-poster
    environment:
      - TZ=America/New_York
    restart: unless-stopped
    volumes:
      - ${PWD}/da_config.json:/usr/src/app/da_config.json
      - ./images:/usr/src/app/images
```

