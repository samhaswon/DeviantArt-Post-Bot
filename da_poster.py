import re
import time

import requests
from typing import List


class Poster:
    STASH_UPLOAD_URL = "https://www.deviantart.com/api/v1/oauth2/stash/submit"
    STASH_PUBLISH_URL = "https://www.deviantart.com/api/v1/oauth2/stash/publish"

    def upload_and_submit(self,
                          file_path: str,
                          token: str,
                          title: str,
                          artist_comments: str,
                          tags: List[str],
                          folders: List[str],
                          is_mature: bool = True,
                          debug: bool = False,
                          back_off_time: int = 2,
                          ) -> None:
        """
        Upload and submit an image to Deviantart.
        :param file_path: Path to the file to upload.
        :param token: The `access_token` to be used for the upload.
        :param title: The title of the deviation.
        :param artist_comments: The comment body of the deviation.
        :param tags: The tags of the deviation.
        :param folders: The folders to post the deviation in to.
        :param is_mature: If the deviation should be tagged as mature.
        :param debug: Print debugging information.
        :param back_off_time: Time to wait for the rate limit to expire.
        :return: None
        """
        # Truncate title
        title = title[:50]
        # Upload image
        params = {
            "access_token": token,
            "title": title,
            "artist_comments": artist_comments,
            "is_mature": is_mature,
        }
        if len(params["artist_comments"]) <= 1:
            del params["artist_comments"]

        encoded_tags = {f"tags[{i}]": tag for i, tag in enumerate(tags)}
        data = {**params, **encoded_tags}
        with open(file_path, "rb") as image_file_pointer:
            image_file = image_file_pointer.read()
            if re.search(r"\.jpe?g$", file_path):
                files = {
                    'image': ('image.jpg', image_file, 'image/jpeg')
                }
            elif re.search(r"\.png$", file_path):
                files = {
                    'image': ('image.png', image_file, 'image/png')
                }
            else:
                raise RuntimeError(f"Invalid file type for file at {file_path}")

        result = requests.post(self.STASH_UPLOAD_URL, data=data, files=files)
        upload_status = result.status_code
        if debug:
            print(f"Raw {result.text=}")
        try:
            result = result.json()
        except requests.exceptions.JSONDecodeError or requests.exceptions.InvalidJSONError:
            json_parsing_failed = True
        else:
            json_parsing_failed = False
        if json_parsing_failed or result.get("status", "failure") != "success":
            if upload_status == 429:
                print(f"Rate limit encountered. Backing off for {back_off_time} seconds.")
                time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time ** 2
                )
            elif upload_status >= 500:
                print(f"Deviantart had a server error {upload_status}. Waiting and trying again", end="")
                for i in range(3):
                    time.sleep(20)
                    print(".", end="")
                print()
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time ** 2
                )
            else:
                raise RuntimeError(f"Unable to upload image!\n"
                                   f"{result=}")
        if debug:
            print(f"JSON parsed {result=}")

        # Post image
        params = {
            "access_token": token,
            "allow_free_download": True,
            "add_watermark": False,
            # "catpath": "visual_art",
            "feature": "true",
            "galleryids": folders,
            "request_critique": False,
            "allow_comments": True,
            "display_resolution": 0,
            "sharing": "allow",
            "license_options": {
                "creative_commons": False,
                "commercial": False,
                "modify": "no"
            },
            "itemid": result["itemid"]
        }
        if is_mature:
            # Some safe defaults for mature content
            params["is_mature"] = True
            params["mature_level"] = "strict"
            params["mature_classification"] = ["nudity", "sexual"]

        post_result = requests.post(self.STASH_PUBLISH_URL, params=params)
        if post_result.status_code > 399:
            if post_result.status_code == 400:
                print("Deviantart broke most likely. Reattempting upload. You may also want to check your stash.")
                print(f"Response:\n{post_result.text=}")
                time.sleep(back_off_time)
                self.upload_and_submit(
                    file_path,
                    token,
                    title,
                    artist_comments,
                    tags,
                    folders,
                    is_mature,
                    debug,
                    back_off_time ** 2
                )
            elif upload_status == 429:
                retry_count = 1
                while post_result.status_code > 399 and retry_count < 20:
                    print(f"Rate limit encountered. Backing off for {back_off_time} seconds.")
                    time.sleep(back_off_time)
                    post_result = requests.post(self.STASH_PUBLISH_URL, params=params)
                    back_off_time = back_off_time ** 2
                    if post_result.status_code > 399:
                        print(f"Retry count: {retry_count}")
                    retry_count += 1
                if post_result.status_code > 399:
                    print(f"Unable to post deviation {title}")
                    return
            elif post_result.status_code in {500, 503}:
                print(f"Deviantart had a server error {post_result.status_code}. Waiting and trying again")
                retry_count = 1
                while post_result.status_code > 399 and retry_count < 20:
                    print(f"Backing off for {back_off_time} seconds")
                    time.sleep(back_off_time)
                    post_result = requests.post(self.STASH_PUBLISH_URL, params=params)
                    back_off_time = back_off_time ** 2
                    if post_result.status_code > 399:
                        print(f"Retry count: {retry_count}")
                    retry_count += 1
                if post_result.status_code > 399:
                    print(f"Unable to post deviation {title}")
                    return
            else:
                raise RuntimeError(f"Failed to post image with error {post_result.status_code} {post_result.reason}\n"
                                   f"{post_result.text}")
        if debug:
            print(f"{post_result.text=}")
        try:
            post_result = post_result.json()
        except requests.exceptions.JSONDecodeError or requests.exceptions.InvalidJSONError:
            print("Failed to post stashed deviation. "
                  "Trying the whole thing again. "
                  "You may also want to check your stash.")
            self.upload_and_submit(
                file_path,
                token,
                title,
                artist_comments,
                tags,
                folders,
                is_mature,
                debug,
                back_off_time ** 2
            )
        else:
            print(f"Successfully posted deviation {post_result['deviationid']} at {post_result['url']}")

