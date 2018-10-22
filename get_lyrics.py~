import sys
import LyricsGenius.lyricsgenius as genius
import logging
logging.basicConfig(filename='errors.log', level=logging.DEBUG, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

names_file = sys.argv[1]
print(names_file)

api = genius.Genius("wt4ySpdIJB7AgYXEtoqinAwGspJL9oZnWxLzERARq1Ymz9b3Ly9-KF20j7XtNWav")
file = open(names_file, "r")
names = file.readlines()
names = list(set([name.strip() for name in names]))
print(names)
for name in names:
	try:
		artist = api.search_artist(name)
		artist.save_lyrics()
	except Exception as e:
		artist.save_lyrics()
		logging.error(name + " encountered an error, but saved progress to file anyway:")
		logging.error(e)
