from mycroft.skills.core import MycroftSkill
from mycroft.util.log import LOG
from mycroft import intent_file_handler
from mycroft.audio import wait_while_speaking
import mycroft.client.enclosure.display_manager as DisplayManager
from .PodcastButler import PodcastButler
import vlc



__author__ = 'martymulligan'


# The logic of each skill is contained within its own class, which inherits
# base methods from the MycroftSkill class with the syntax you can see below:
# "class ____Skill(MycroftSkill)"
class PodcastButlerSkill(MycroftSkill):

    # The constructor of the skill, which calls MycroftSkill's constructor
    def __init__(self):
        MycroftSkill.__init__(self)
        self.ducking = False
        self.idle_count = 0

    def initialize(self):
        self.player = None
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

    @intent_file_handler('listen.intent')
    def handle_listen_intent(self, message):
        if 'show' not in message.data:
            self.speak_dialog("not.sure");
            return

        show = message.data["show"]
        pb = PodcastButler()
        podcast = pb.find_podcast(show)

        if podcast is not None:
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

    # The "stop" method defines what Mycroft does when told to stop during
    # the skill's execution. In this case, since the skill's functionality
    # is extremely simple, the method just contains the keyword "pass", which
    # does nothing.
    def stop(self):
        self.stop_playback()


# The "create_skill()" method is used to create an instance of the skill.
# Note that it's outside the class itself.
def create_skill():
    return PodcastButlerSkill()
