from datetime import datetime, timedelta
import json
import os
import re
import sched
import time
from typing import List, Union

from da_token_manager import DATokenManager
from da_poster import Poster, OAuthError


# Global stuff
TOKEN: str = ""
DEBUG: bool = True
DEBUG_NO_POST: bool = True

# Load config
with open("da_config.json", "r") as json_file:
    da_config_dict: dict = json.load(json_file)
    for key in da_config_dict.keys():
        if isinstance(da_config_dict[key], int):
            da_config_dict[key] = str(da_config_dict[key])
    DEBUG = eval(da_config_dict.get("debug", "True"))
    DEBUG_NO_POST = eval(da_config_dict.get("debug_no_post", "True"))

# Set up the token manager and poster
token_manager = DATokenManager(da_config_dict, debug=DEBUG)
TOKEN = token_manager.token     # keep this up to date during testing
poster = Poster()

# Initialize the scheduler
scheduler = sched.scheduler(time.time, time.sleep)


def update_token() -> None:
    """
    Makes sure the token is valid. Call this before performing an action on the API.
    :return: None
    """
    global TOKEN
    TOKEN = token_manager.token


def resolve_tags(post_config: dict, post_index: int | None = None) -> List[str]:
    """
    Normalize tag configuration into a list of tag strings.
    Daily posts use a flat list. Rotation posts may use either a flat list shared
    across all directories or a list-of-lists keyed by rotation index.
    :param post_config: A single post_config entry from the JSON file.
    :param post_index: Active rotation index when relevant.
    :return: A list of tag strings.
    """
    tags = post_config["tags"]
    if isinstance(tags, list) and tags and isinstance(tags[0], list):
        if post_index is None:
            raise ValueError("Rotation tag groups require a post index.")
        return tags[post_index]
    return tags


def make_post(directory: str,
              num_images: int,
              galleries: List[str],
              tags: List[str],
              is_ai: Union[str, bool],
              artist_comments_prepend: str = "") -> None:
    """
    Make a post to DeviantArt using the relevant parameters.
    :param directory: The directory to post from.
    :param num_images: The number of images to post.
    :param galleries: The galleries to post to.
    :param tags: The tags to use for the image(s).
    :param is_ai: Whether the image is an AI or not.
    :param artist_comments_prepend: Text to prepend to the image's artist comments.
    :return: None.
    """
    if not os.path.isdir(directory):
        print(f"{directory} is not a directory!")
        return
    files = [
        x for x in os.scandir(directory)
        if os.path.isfile(x.path) and re.search(r"\.jpe?g$|\.png$", x.path)
    ]
    if len(files) == 0:
        print(f"Out of files to post in {directory}")
        return

    files.sort(key=lambda x: int(re.sub(r"\D", '', x.name)))

    # Extract only the number of files we're posting
    files = files[:num_images]

    if DEBUG:
        print(f"Posting files: {files}")

    update_token()
    for file in files:
        base_name = file.name[:file.name.rfind(".")]
        base_path = file.path[:file.path.rfind(".")]
        if os.path.isfile(base_path + ".txt"):
            with open(base_path + ".txt", "r") as comment_file:
                comment = comment_file.read()
        else:
            comment = ""
        comment = artist_comments_prepend + comment
        post_name = re.sub(r"_+|\s\s+", " ", base_name)
        if DEBUG:
            print(f"Posting {post_name} from {file.path}\n"
                  f"with {comment=}; {tags=}; {galleries=}")

        # Post the image
        if not DEBUG_NO_POST:
            submitted: bool = False
            while not submitted:
                try:
                    poster.upload_and_submit(file.path,
                                             TOKEN,
                                             post_name,
                                             comment,
                                             tags,
                                             galleries,
                                             is_ai_generated=is_ai,
                                             debug=DEBUG)
                    submitted = True
                except OAuthError:
                    update_token()
            os.remove(file.path)


def post_scheduler() -> None:
    """
    Schedules posts to happen based on the configuration file.
    :return: None.
    """
    global da_config_dict, scheduler
    for post_type in da_config_dict["post_config"].keys():
        post_config = da_config_dict["post_config"][post_type]
        posting_type = post_config["type"]
        if posting_type.lower() == "rotation":
            # Take advantage of the fact that the token manager has a shallow copy of the dictionary
            post_config["last_posted"] += 1
            # token_manager.extra_config["post_config"][post_type]["last_posted"] += 1
            if post_config["last_posted"] >= len(post_config["directories"]):
                post_config["last_posted"] = 0
                # token_manager.extra_config["post_config"][post_type]["last_posted"] = 0
            token_manager.increment_rotation_config(post_type, post_config["last_posted"])

            # Figure out what we're posting
            post_index = post_config["last_posted"]
            directory = post_config["directories"][post_index]
            tags = resolve_tags(post_config, post_index)

        elif posting_type.lower() == "daily":
            # Figure out what we're posting
            directory = post_config["directory"]
            tags = resolve_tags(post_config)

        else:
            print(f"Invalid configuration for posting type: {posting_type}")
            exit(1)

        # Grab common config arguments
        images_per_day: int = post_config["images_per_day"]
        time_of_day: str = post_config["time"]
        galleries: List[str] = post_config["galleries"]
        is_ai: Union[str, bool] = post_config["is_ai"]
        artist_comments_prepend: str = post_config.get("artist_comments_prepend", "")

        # Figure out when to schedule the posting
        hour, minute = tuple(time_of_day.split(":"))
        hour, minute = int(hour), int(minute)
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If the target time is already past today, schedule for tomorrow
        if target_time <= now:
            target_time += timedelta(days=1)
        delay = (target_time - now).total_seconds()
        scheduler.enter(
            delay,
            1,
            make_post,
            argument=(directory, images_per_day, galleries, tags, is_ai, artist_comments_prepend)
        )
        print(f"Scheduled posting of {post_type} for {target_time}")


def run_scheduler() -> None:
    """
    The main post scheduling loop.
    :return: None.
    """
    while True:
        # Schedule the task
        post_scheduler()

        # Run the scheduler
        scheduler.run()

        # Wait for one hour before checking again
        time.sleep(3600)


if __name__ == '__main__':
    # Print config information
    print(f"{DEBUG=}\n{DEBUG_NO_POST=}")
    print("Config\n", "-" * 20, "\n")
    for post_type in da_config_dict["post_config"].keys():
        print(json.dumps(da_config_dict["post_config"][post_type], indent=4))
    print("\n", "-" * 20, "\n")

    # Get everything going
    run_scheduler()
