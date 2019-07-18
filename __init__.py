from mycroft.skills.core import MycroftSkill
from mycroft.util.log import LOG
from mycroft import intent_file_handler
from mycroft.audio import wait_while_speaking
import mycroft.enclosure.display_manager as DisplayManager
from .PodcastButler import PodcastButler
import vlc
import datetime
import pprint



__author__ = 'martymulligan'


class PodcastButlerSkill(MycroftSkill):

    # The constructor of the skill, which calls MycroftSkill's constructor
    def __init__(self):
        MycroftSkill.__init__(self)
        self.ducking = False
        self.idle_count = 0
        self.player = None

    def initialize(self):
        self.reset_now_playing()

    def pb(self):
        if self.butler is None:
            self.butler = PodcastButler()
        return self.butler

    def reset_now_playing(self):
        self.current_podcast = None
        self.current_episode = None

    def save_playback_state(self):
        try:
            episode_key = self._get_episode_key(self.current_podcast, self.current_episode)
            history_key = self._get_history_key(self.current_podcast)
            self.settings[episode_key] = self.player.get_time()
            self.settings[history_key] = self.current_episode.guid
        except KeyError as e:
            LOG.info(repr(e))

    def _get_history_key(self, podcast):
        return podcast.url + "--recent_episode"

    def _get_episode_key(self, podcast, episode):
        return podcast.url + "--" + episode.guid

    def load_podcast_recent_episode(self, podcast):
        history_key = self._get_history_key(podcast)
        episode_guid = self.settings.get(history_key)
        episode = None
        if episode_guid is not None:
            episode = next((ep for ep in podcast.items if ep.guid == episode_guid), None)
        return episode

    def load_episode_playback_state(self, podcast, episode):
        episode_key = self._get_episode_key(podcast, episode)
        return self.settings.get(episode_key, 0)

    def play_episode(self, podcast, episode):
        try:
            if self.player is not None and self.player.is_playing():
                self.stop_playback()

            self.current_podcast = podcast
            self.current_episode = episode
            url = episode.enclosure_url
            LOG.info(url)

            playback_position = self.load_episode_playback_state(podcast, episode)
            LOG.info("Starting at " + str(playback_position) + " for [" + episode.guid + "] " + episode.title)

            if playback_position > 0:
                self.speak_dialog("resume", {"episode_title": episode.title})
            else:
                self.speak_dialog("playing",  {"episode_title": episode.title})

            wait_while_speaking()
            self.player = vlc.MediaPlayer(episode.enclosure_url)
            self.add_event('recognizer_loop:record_begin', self.handle_listener_started)
            self.player.play()
            self.player.set_time(playback_position)
        except Exception as e:
            LOG.error("Playback position type is "+type(playback_position))
            LOG.error(str(playback_position))
            self.reset_now_playing()

    def pause_playback(self):
        if self.player is not None:
            self.player.set_pause(1)
            self.save_playback_state()

    def resume_playback(self):
        if self.player is not None:
            self.player.set_pause(0)
        else:
            self.speak_dialog("no.podcast.action", {"action": "resume playing"})

    def stop_playback(self):
        if self.player is not None:
            self.save_playback_state()
            self.player.stop()
            return True
        else:
            return False

    ######################################################################
    # Handle auto ducking when listener is started.

    def handle_listener_started(self, message):
        """ Handle auto ducking when listener is started. """
        if self.player.is_playing():
            self.pause_playback()
            self.ducking = True

            # Start idle check
            self.idle_count = 0
            self.cancel_scheduled_event('IdleCheck')
            self.schedule_repeating_event(self.check_for_idle, None,
                                          1, name='IdleCheck')

    def check_for_idle(self):
        """ Repeating event checking for end of auto ducking. """
        if not self.ducking:
            self.cancel_scheduled_event('IdleCheck')
            return

        active = DisplayManager.get_active()
        if not active == '' or active == 'PodcastButlerSkill':
            # No activity, start to fall asleep
            self.idle_count += 1

            if self.idle_count >= 5:
                # Resume playback after 5 seconds of being idle
                self.cancel_scheduled_event('IdleCheck')
                self.ducking = False
                self.resume_playback()
        else:
            self.idle_count = 0

    ######################################################################
    # ###
    # ### Intent Handlers
    # ###

    @intent_file_handler('list.intent')
    def handle_list_intent(self, message):
        if 'show' not in message.data:
            if self.current_podcast is None:
                self.speak_dialog("not.sure");
                return
            else:
                podcast = self.current_podcast
        else:
            show = message.data["show"]
            podcast = PodcastButler().find_podcast(show)

        show = podcast.title
        LOG.info(podcast.__dict__)
        count = len(podcast.items) if len(podcast.items) < 5 else 5
        episodes = ""
        for i in range(0, count):
            episodes += str(i+1) + ", " + podcast.items[i].title + ". "
        self.speak_dialog("episode.list", {"show": show, "episodes": episodes})
        self.speak("That is all")

        LOG.info(message.data)

    @intent_file_handler('get.info.intent')
    def handle_list_intent(self, message):
        if 'show' not in message.data:
            if self.current_podcast is None:
                self.speak_dialog("not.sure");
                return
            else:
                podcast = self.current_podcast
        else:
            show = message.data["show"]
            podcast = PodcastButler().find_podcast(show)

        # LOG.info(podcast.__dict__)
        count = len(podcast.items)
        latest = podcast.get_episode(0)

        days = {
            1: "first",
            2: "second",
            3: "third",
            4: "fourth",
            5: "fifth",
            6: "sixth",
            7: "seventh",
            8: "eighth",
            9: "ninth",
            10: "tenth",
            11: "eleventh",
            12: "twelfth",
            13: "thirteenth",
            14: "fourteenth",
            15: "fifteenth",
            16: "sixteenth",
            17: "seventeenth",
            18: "eighteenth",
            19: "nineteenth",
            20: "twentieth",
            21: "twenty first",
            22: "twenty second",
            23: "twenty third",
            24: "twenty fourth",
            25: "twenty fifth",
            26: "twenty sixth",
            27: "twenty seventh",
            28: "twenty eighth",
            29: "twenty ninth",
            30: "thirtieth",
            31: "thirty first"
        }
        spoken_month = latest.date_time.strftime("%B")
        spoken_day = days.get(int(latest.date_time.strftime("%d")), "")
        spoken_year = latest.date_time.strftime("%Y")
        pubdate =  "{} {} {}".format(spoken_month, spoken_day, spoken_year)

        self.speak_dialog("podcast.info", {"podcast": podcast, "count": count, "pubdate": pubdate})


    @intent_file_handler('listen.intent')
    def handle_listen_intent(self, message):
        if 'show' not in message.data:
            self.speak_dialog("not.sure");
            return

        show = message.data["show"]
        podcast = PodcastButler().find_podcast(show)
        utt = message.data.get('utterance') or ""

        if podcast is not None:
            episode = None
            if "latest episode" not in utt and "recent episode" not in utt:
                episode = self.load_podcast_recent_episode(podcast)
            if episode is None:
                episode = podcast.get_episode(0)
            self.play_episode(podcast, episode)
        else:
            self.speak_dialog("no.podcast.found", {"show": show})

    @intent_file_handler('episode.next.intent')
    def handle_episode_next_intent(self, message):
        self.stop_playback()
        pb = PodcastButler()
        if 'show' in message.data:
            podcast = pb.find_podcast(message.data['show'])
        elif self.current_podcast is not None:
            podcast = self.current_podcast
        else:
            self.speak_dialog("no.podcast.action", {"action": "play the next episode for"})
            return

        recent_episode = self.load_podcast_recent_episode(podcast)
        if recent_episode is None:
            next_episode = podcast.items[0]
        else:
            episode_idx = podcast.items.index(recent_episode)
            try:
                next_idx = episode_idx+1
                next_episode = podcast.items[next_idx]
            except KeyError:
                self.speak_dialog("no.episodes")
                return
        self.play_episode(podcast, next_episode)

    @intent_file_handler('episode.previous.intent')
    def handle_episode_previous_intent(self, message):
        self.stop_playback()
        pb = PodcastButler()
        if 'show' in message.data:
            podcast = pb.find_podcast(message.data['show'])
        elif self.current_podcast is not None:
            podcast = self.current_podcast
        else:
            self.speak_dialog("no.podcast.action", {"action": "play the previous episode for"})
            return

        recent_episode = self.load_podcast_recent_episode(podcast)
        if recent_episode is None:
            prev_episode = podcast.items[0]
        else:
            episode_idx = podcast.items.index(recent_episode)
            try:
                prev_idx = episode_idx - 1
                prev_episode = podcast.items[prev_idx]
            except KeyError:
                self.speak_dialog("no.episodes.first")
                return
        self.play_episode(podcast, prev_episode)

    @intent_file_handler('pause.intent')
    def handle_pause_intent(self, message):
        self.pause_playback()

    @intent_file_handler('resume.intent')
    def handle_resume_intent(self, message):
        self.resume_playback()


    def stop(self):
        self.stop_playback()


# The "create_skill()" method is used to create an instance of the skill.
# Note that it's outside the class itself.
def create_skill():
    return PodcastButlerSkill()
