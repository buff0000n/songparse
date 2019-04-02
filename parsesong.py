#!/usr/bin/python
# parsesong.py <path to EE.log>
# Tool for parsing through Warframe's EE.log file for Mandachord Songs that you have
# posted to chat since last starting the game.
# Author: Buff00n
# Disclaimer: I literally haven't written any Python in 15 years

import sys
import re
import base64

# mapping from instrument pack identifiers to their name as they appear in game 
mapping = {
	"BardTennoPackA" : "Adau",
	"BardCorpusPackA" : "Alpha",
	"BardCorpusPackB" : "Beta",
	"BardCorpusPackD" : "Delta",
	"BardGrineerPackA" : "Druk",
	"BardCorpusPackE" : "Epsilon",
	"BardCorpusPackC" : "Gamma",
	"BardEDMPackA" : "Horos",
	"BardGrineerPackB" : "Plogg"
}

# get the mapped in-game name from an instrument set identifier, or just the identifier if we
# don't have a mapping
def getPackName(id):
	if id in mapping:
		# got a mapping
		return mapping[id]
	else:
		# unknown instrument set pls update kthxbye
		return id

# consider a byte array to be divided into a bit matrix with the given number of columns in each row,
# then access a single bit with its row and column position
def getBit(bytes, numColumns, row, column, littleendian, offset): 
	# get the bit index in the bit array
	bit = (row * numColumns) + column
	# convert the bit index into a byte index, taking into account the offset
	byteIndex = offset + (bit >> 3) 
	# and a sub index inside that byte
	bitIndex = bit & 0x07 
	# if it's little endian then we need to count from the other end of the byte
	if littleendian: 
		bitIndex = 7 - bitIndex
	# if the byte index is past the end of the array then assume it's zero
	if byteIndex >= len(bytes): 
		return 0 
	else:
		# extract the bit from inside the byte
		return (bytes[byteIndex] >> bitIndex) & 0x01

# turn volume data into something human readable
def getVolume(b1, b2):
	# I seriously cannot figure out the number format for the volume sliders

	# I know that all zeros means 100% volume
	if b1 == 0 and b2 == 0:
		return "100%"

	# I know that this inscrutable string of bits means 0% volume
	if b1 == 0xD1 and b2 == 0xD2:
		return "0%"
	
	# Everything else, even if you move off 100% by just a tiny bit, 
	# is a seemingly random string of bits that makes no pattern that I can see.
	# It's not fixed point, floating point, packed decimal, or even ascii digits.  
	# I don't know if it's some Lua thing or what, but I give up.
	return "?%"

# take the regex matcher and convert the pieces into a reasonable imitation of how
# songs appears in game
def parseSong(match):
	# name is first in the block
	name = match.group(1);
	# followed by a bunch of base64 encoded binary data
	encoded = match.group(2);
	# followed by instrument sets identifiers, in reverse order
	percInst = getPackName(match.group(5));
	bassInst = getPackName(match.group(4));
	melodyInst = getPackName(match.group(3));

	# Why is it so hard to just get a list of numbers?
	# This works, but I have to wrap every b[n] with ord(b[n]) to get a number.
	b = base64.standard_b64decode(encoded)

	# the first six bytes are the volume sliders for each instrument part
	# two bytes each, in reverse order
	percVolume = getVolume(b[4], b[5])
	bassVolume = getVolume(b[2], b[3])
	melodyVolume = getVolume(b[0], b[1])

	# Get these out of the way
	print ("Name: " + name)
	print ("Percussion: " + percInst + ": " + percVolume)
	print ("Bass: " + bassInst + ": " + bassVolume)
	print ("Melody: " + melodyInst + ": " + melodyVolume)

	# After the first 6 bytes, the note data is packed bit by bit into 13*64 bits.
	# The first 13 bits are the first vertical column in the first measure of the song, 
	# starting at the bottom melody note and ending at the top percussion note.  
	# 1 indicates that note is filled, 0 means it's blank.
	# The next 13 bits are the second vertical column in the first measure.  This continues
	# for all 64 columns.
	# This is probably convenient for playback, but the binary data columns and rows are 
	# reversed compared to how the note data appears in the game.  I need to reverse the rows
	# and columns, and the easiest way was to just build a random bit access method getBit()
	# Other tidbits:
	#   The bytes themselves are little endian for some reason, so that has to be reversed too.
	#   If the last columns of the song are blank then their data will be truncated and not 
	#     included in the song's base64 data.  If you share a completely blank song then the 
	#     base64 data will only include the six bytes of volume slider data.

	# header divider for note data
	print ("-----------1--------------------2--------------------3--------------------4-----------")
	       
	# count down from 12 to 0, because the data columns are in reverse order from how the note rows
	# appear in game
	for c in range(12, -1, -1):
		# for each data column/note row, count up through the 64 data rows/note columns 
		for r in range(0, 64):
			if (r % 16 == 0):
				# print the measure dividers every sixteen notes
				# printing without ending it with a newline is surprisingly hard
				sys.stdout.write("||")
			elif (r % 4 == 0):
				# print the quarter note dividers every four notes
				sys.stdout.write("|")
			# check the bit at the current data row and column/note column and row
			if getBit(b, 13, r, c, 1, 6) == 1:
				# write a "O" for filled notes
				sys.stdout.write("O")
			else:
				# write a "." for blank notes
				sys.stdout.write(".")
		# not sure if I need this
		sys.stdout.flush()
		# print the last measure separator and end the line
		print ("||")

		# print instrument set separators after data column/note 10 (between bass and percussion)
		# and row 5 (between melody and bass) (note that c is counting down from 12)
		if (c == 10 or c == 5):
			print ("--------------------------------------------------------------------------------------")
	# final footer divider for note data
	print ("--------------------------------------------------------------------------------------")


# The actual program starts here

# get the filename from the command line
filename = sys.argv[1]

# open the file
with open(filename, 'r', errors='replace') as f:
	# compile a regular expression that matches the [SONG-...] format.  It looks like this:
	# [SONG-<song name>:<base 64 data>:<melody instrument>:<bass instrument>:<percussion instrument>]
	pat = re.compile('\[SONG-([^:]+):([^:]+):([^:]+):([^:]+):([^:\]]+)\]')
	# read the file line by line
	for line in f.readlines():
		# search for a song.  I'm assuming there is only one per line
		match = pat.search(line)
		if match != None: 
			# print the raw [SONG-...] data for posterity
			print (match.group(0))
			# run the parser
			parseSong(match)
# done
