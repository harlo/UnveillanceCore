from collections import namedtuple

EmitSentinel = namedtuple("EmitSentinel", "attr type s_replace")
AnnexDescriptor = namedtuple("AnnexDescriptor", "farm p22 p8888")

mime_types = namedtuple("mime_types", "TEXT EVALUATE")
MimeTypes = mime_types("plain/txt", ["plain/txt"])

asset_tags = namedtuple("asset_tags", "ORIG F_MD")
AssetTags = asset_tags("original_document", "metadata_fingerprint")

class Result(object):
	def __init__(self):
		self.result = 404

	def emit(self): return self.__dict__