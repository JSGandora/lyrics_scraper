import sys
from os import listdir
import os.path
import LyricsGenius.lyricsgenius as genius
import logging
import threading
import re
logging.basicConfig(filename='errors.log', level=logging.DEBUG, 
					format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

names_file = sys.argv[1]
genre = names_file.split(".")[0]
print("Genre Name: " + genre)
n_threads = int(sys.argv[2])
access_token = sys.argv[3]
print(names_file)

api = genius.Genius(access_token)
file = open(names_file, "r")
names = file.readlines()
names = list(set([name.strip() for name in names]))
print(names)


def save_artist_songs(name):
	try:
			if os.path.isfile("lyrics/" + genre + "/" + name + ".json"):
					print(name + " has already been queried.");
					logging.error(name + " is already queried and saved.")
					return
			else:
				artist = api.search_artist(name)
				artist.save_lyrics(filename="lyrics/" + genre +"/" + name)
	except Exception as e:
		artist.save_lyrics(filename="lyrics/" + genre + "/" + name)
		logging.error(name + " encountered an error, but saved progress to file anyway:")
		logging.error(e)


i = 0
while i < len(names):
	threads = [None] * n_threads
	j = 0
	while j < n_threads and i < len(names):
		threads[j] = threading.Thread(target = save_artist_songs, args=(names[i],))
		j += 1
		i += 1

	for k in range(j):
		threads[k].start()

	for k in range(j):
		threads[k].join()
