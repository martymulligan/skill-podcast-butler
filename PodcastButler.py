from pyPodcastParser.Podcast import Podcast
import requests
import urllib.parse
import inspect
import pprint

class PodcastButler:

    # def __init__(self):
    #     res = self.find_podcast('on the media')
    #     pprint.pprint(res)

    def find_podcast(self, show):
        params = {
            "attribute": "titleTerm",
            "term": show,
            "media": "podcast"
        }
        params = urllib.parse.urlencode(params)
        url = 'https://itunes.apple.com/search?'+params
        response = requests.get(url)
        json = response.json()
        result = json['results'][0];
        feed_url = result['feedUrl']

        podcast = PodcastButlerPodcast(feed_url)
        return podcast


    def get_track(selfs, podcast, item):
        podcast_url = podcast.url

class PodcastButlerPodcast(Podcast):
    def __init__(self, url):
        self.url = url
        feed_response = requests.get(url)
        Podcast.__init__(self, feed_response.content)

    def get_episode(self, episode_idx):
        try:
            item = self.items[episode_idx]
        except IndexError as e:
            item = None
        return item