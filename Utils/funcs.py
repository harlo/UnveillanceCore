import os, sys, signal, json, re, string, random, base64, urllib
from time import time
from subprocess import Popen, PIPE
from hashlib import md5, sha1, sha256

from Crypto.Cipher import AES
from Crypto import Random

from vars import UNCAUGHT_UNICODES, UNCAUGHT_PUNCTUATION, STOPWORDS, SPLITTERS
from conf import DEBUG, SHA1_INDEX

def hours_to_seconds(hours):
	return (hours * 60 * 60)

def days_to_seconds(days):
	return hours_to_seconds(24)

def b64decode(content):
	try:
		return base64.b64decode(content)
	except TypeError as e:
		if DEBUG: 
			print e
			print "...so trying to decode again (brute-force padding)"
			
		try:
			return base64.b64decode(content + ("=" * ((4 - len(content) % 4) % 4)))
		except TypeError as e:
			if DEBUG: print "could not unB64 this content: %s"  % e
	
	return None

def cleanLine(line):
	line = line.strip()
	try:
		line = line.decode('utf8')
	except Exception as e:
		print "clean line error", e

	for u in UNCAUGHT_UNICODES:
		line = re.sub(u.regex, " " if u.sub is None else u.sub, line)
	
	return line

def cleanAndSplitLine(line):
	line = cleanLine(line)
	
	for c in UNCAUGHT_PUNCTUATION:
		line = re.sub(c.regex, " " if c.sub is None else c.sub, line)
	
	line = line.lower()
	words = list(set(re.split(SPLITTERS, line)))
	
	# remove stopwords, numbers, nochars
	words = [word for word in words if word != ""]
	words = [word for word in words if re.match(r'\b([a-zA-Z]+)\b', word) is not None]
	words = [word for word in words if word not in STOPWORDS]
	
	return words

def asTrueValue(str_value):
	try:
		if str_value.startswith("[") and str_value.endswith("]"):
			vals = []
			for v_ in str(str_value[1:-1]).split(","):
				vals.append(asTrueValue(v_))

			return vals
		if str_value.startswith("{") and str_value.endswith("}"):
			return json.loads(str_value)
		if str_value == "0":
			return int(0)
		if str_value == "true":
			return True
		if str_value == "false":
			return False
		if type(str_value) is unicode:
			return unicode.join(u'\n', map(unicode, str_value))
	except AttributeError:
		pass
	
	try:
		if int(str_value):
			return int(str_value)
	except ValueError:
		pass
		
	try:
		if float(str_value):
			return float(str_value)	
	except ValueError:
		pass
		
	return str_value

def getTrueValue(str_value):
	str_value = str(str_value)
	if str_value.startswith("[") and str_value.endswith("]"):
		return 'list'
	if str_value == "0":
		return 'int'
	if str_value == "true" or str_value == "false":
		return 'bool'
	try:
		if int(str_value):
			return 'int'
	except ValueError as e:
		#print "GET TRUE VALUE ERROR: %s so i returned i try float " % e
		pass
		
	try:
		if float(str_value):
			return 'float'
	except ValueError as e:
		#print "GET TRUE VALUE ERROR: %s so i returned i return str " % e
		pass
		
	return 'str'
	
def unUnicode(data):
	return asTrueValue(unicode.join(u'\n', map(unicode, data)))

def passesParameterFilter(param_str):
	# WHY EVEN TRY??? TODO: there is a package for you here.
	# looking for pipes
	match = re.search(r'\s*\|\s*.+', param_str)
	if match:
		print "found a pipe:\n%s" % match.group()
		return False

	# looking for two periods and slashes "\..\"
	match = re.search(r'\.\./', param_str)
	if match:
		print "found a file inclusion attempt:\n%s" % match.group()
		return False

	# looking for XSS using broken element tags (i.e. <svg/onload=alert(1)>
	match = re.search(r'<\s*\w+/\s*.+=.*\s*>', param_str)
	if match:
		print "found an XSS attempt using broken element tag:\n%s" % match.group()	
		return False

	return True

def parseRequestEntity(entity):
	# if query string is already json, return that
	print "\n\nENTITY:\n%s\n%s" % (entity, urllib.unquote(entity))
	print type(entity)
	
	try:
		if passesParameterFilter(entity):
			return json.loads(entity)
		else: return None
	except ValueError as e: pass
	
	# otherwise...
	# TODO: does this need to be so bespoke? can we use urlparse?
	params = dict()
	for kvp in [w for w in urllib.unquote(entity).split("&") if w != ""]:
		kvp = kvp.split("=")
		k = kvp[0]
		v = kvp[1]
		
		if not passesParameterFilter(k) or not passesParameterFilter(v):
			return None

		# TODO: you have some dicts in here, too!
		
		params[k] = asTrueValue(v)
	
	return params

def hashEntireFile(path_to_file, hfunc=None):
	try:
		if hfunc is None:
			if not SHA1_INDEX:
				m = md5()
			else:
				m = sha1()
		elif hfunc == "md5":
			m = md5()
		elif hfunc == "sha1":
			m = sha1()
		elif hfunc == "sha256":
			m = sha256()

		with open(path_to_file, 'rb') as f:
			for chunk in iter(lambda: f.read(4096), b''):
				m.update(chunk)
		return m.hexdigest()
	
	except: pass
	return None

def hashEntireStream(stream, hfunc=None):
	stream.seek(0, os.SEEK_SET)
	try:
		if hfunc is None:
			if not SHA1_INDEX:
				m = md5()
			else:
				m = sha1()
		elif hfunc == "md5":
			m = md5()
		elif hfunc == "sha1":
			m = sha1()
		elif hfunc == "sha256":
			m = sha256()

		for chunk in iter(lambda: stream.read(4096), b''):
			m.update(chunk)
		return m.hexdigest()
	
	except Exception as e:
		print "ERROR HASHING STREAM:"
		print e
		pass
		
	return None

def startDaemon(log_file, pid_file):
	print "DAEMONIZING PROCESS>>>"
	try:
		pid = os.fork()
		if pid > 0:
			sys.exit(0)
	except OSError, e:
		print e.errno
		sys.exit(1)
		
	os.chdir("/")
	os.setsid()
	os.umask(0)
	
	try:
		pid = os.fork()
		if pid > 0:
			f = open(pid_file, 'w')
			f.write(str(pid))
			f.close()
			
			sys.exit(0)
	except OSError, e:
		print e.errno
		sys.exit(1)
	
	si = file('/dev/null', 'r')
	so = file(log_file, 'a+')
	se = file(log_file, 'a+', 0)
	os.dup2(si.fileno(), sys.stdin.fileno())
	os.dup2(so.fileno(), sys.stdout.fileno())
	os.dup2(se.fileno(), sys.stderr.fileno())

	print ">>> PROCESS DAEMONIZED"

def stopDaemon(pid_file, extra_pids_port=None):
	pid = False
	try:
		f = open(pid_file, 'r')
		try:
			pid = int(f.read().strip())
		except ValueError as e:
			print "NO PID AT %s" % pid_file
	except IOError as e:
		print "NO PID AT %s" % pid_file
	
	if pid:
		print "STOPPING DAEMON on pid %d" % pid
		try:
			os.kill(pid, signal.SIGTERM)
			
			if extra_pids_port is not None:
				pids = Popen(['lsof', '-t', '-i:%d' % extra_pids_port], stdout=PIPE)
				pid = pids.stdout.read().strip()
				pids.stdout.close()
				
				for p in pid.split("\n"):
					cmd = ['kill', str(p)]
					Popen(cmd)
			
			return True
		except OSError as e:
			print "could not kill process at PID %d" % pid

	return False

def generateNonce(bottom_range=21, top_range=46):
	
	orderings = [
			string.ascii_uppercase, 
			string.digits, 
			string.ascii_lowercase, 
			string.digits, 
			string.ascii_uppercase,
			'*@~._!$%',
			str(time())
	]
	
	random.shuffle(orderings)
	choices = ''.join(orderings)
	numChars = random.choice(range(bottom_range, top_range))
	
	return ''.join(random.choice(choices) for x in range(numChars))

def generateSecureNonce(bottom_range=40, top_range=80):
	orderings = []
	for x in xrange(5):
		orderings.append(generateSecureRandom())
	
	choices = ''.join(orderings)
	numChars = random.choice(range(bottom_range, top_range))
	return "".join(random.choice(choices) for x in range(numChars))

def generateSecureRandom(try_again=True):
	try:
		return Random.new().read(AES.block_size).encode('hex')
	except AssertionError as e:
		if try_again:
			Random.atfork()
			return generateSecureRandom(try_again=False)
	
	return None
	
def generateMD5Hash(content=None, salt=None):
	if content is None:
		content = generateNonce()
	
	if not SHA1_INDEX:
		m = md5()
	else:
		m = sha1()

	m.update(str(content))
	if salt is not None: m.update(str(salt))
	return m.hexdigest()