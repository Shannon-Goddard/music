"""
Strict genre map — unambiguous aliases only.
If a reasonable person could disagree about the mapping, it's not here.

Imported by apply_genres.py.
"""

GENRE_MAP = [
    ("electronic", {
        "electronic", "electronica", "idm", "intelligent dance music",
        "techno", "house", "deep house", "tech house", "acid house", "chicago house",
        "detroit techno", "minimal techno", "hard techno", "acid techno",
        "trance", "psytrance", "goa trance", "progressive trance",
        "drum and bass", "drum & bass", "drumnbass", "drum n bass", "dnb",
        "breakbeat", "electro", "edm", "electronic dance music",
        "synthwave", "retrowave", "darkwave", "coldwave", "synthpop",
        "chiptune", "8bit", "8-bit", "vaporwave", "eurodance",
        "electrohouse", "electro house", "progressive house",
        "dubstep", "chillstep", "future bass",
        "neurofunk", "liquid funk", "darkstep", "techstep",
        "italo disco", "nu-disco",
        "modular synth", "synthesizer",
        "electronic music",
    }),
    ("ambient", {
        "ambient", "dark ambient", "drone", "soundscape", "soundscapes",
        "space ambient", "ritual ambient", "darkambient", "drone ambient",
        "ambient dub", "space music", "field recording", "field recordings",
        "phonography", "binaural", "nature sounds",
    }),
    ("jazz", {
        "jazz", "free jazz", "nujazz", "nu jazz", "nu-jazz", "swing", "big band",
        "bebop", "smooth jazz", "acid jazz", "jazzfunk", "jazz funk",
        "jazzfusion", "jazz fusion", "gypsy jazz", "manouche",
        "dixieland", "ragtime", "cool jazz", "modal jazz",
        "post-bop", "hard bop", "future jazz", "jazz piano",
        "smoothjazz", "acidjazz", "jazztronica", "latinjazz",
    }),
    ("classical", {
        "classical", "classical music", "orchestral", "opera", "operetta",
        "choral", "symphony", "symphonic", "chamber", "chamber music",
        "baroque", "renaissance", "medieval", "romantic",
        "contemporary classical", "modern classical",
        "string quartet", "orchestral music",
        "early music", "gregorian", "sacred choral",
        "neoclassical",
    }),
    ("blues", {
        "blues", "delta blues", "chicago blues", "electric blues",
        "blues rock", "bluesrock", "blues-rock",
        "swamp blues", "texas blues", "piedmont blues",
        "jump blues", "boogie woogie", "boogie-woogie",
    }),
    ("rock", {
        "rock", "classic rock", "alternative rock", "indie rock", "indie",
        "poprock", "pop rock",
        "garage rock", "psychedelic rock", "progressive rock",
        "post-rock", "post rock", "art rock", "hard rock",
        "rock and roll", "rock n roll", "rock & roll", "rockabilly",
        "stoner rock", "shoegaze", "grunge", "britpop",
        "surf rock", "surfrock", "southern rock", "heartland rock",
        "indierock", "alternativerock", "classicrock", "hardrock",
        "progressiverock", "spacerock", "artrock", "noiserock",
        "postrock", "psychedelicrock", "math rock", "mathrock",
        "gothic rock", "gothicrock", "deathrock", "krautrock",
        "j-rock", "k-rock", "latin rock",
    }),
    ("hip-hop", {
        "hip-hop", "hiphop", "hip hop", "rap",
        "underground rap", "boom bap", "trap", "lofi", "lo-fi",
        "chillhop", "triphop", "trip hop", "trip-hop",
        "jazz rap", "jazzrap", "alternative hip hop", "alternativehiphop",
        "lofi hip hop", "instrumental hip-hop",
    }),
    ("folk", {
        "folk", "folk music", "singer-songwriter", "singersongwriter",
        "neofolk", "folk rock", "folkrock", "anti-folk",
        "freak folk", "dark folk", "irish folk", "scottish folk",
        "appalachian", "bluegrass", "old-time", "oldtime",
        "americana", "celtic",
    }),
    ("country", {
        "country", "country music", "outlaw country", "country rock",
        "countryrock", "traditional country", "country pop",
        "country folk", "country blues", "western swing",
        "honky tonk", "alt-country", "old-time country",
        "traditional/country",
    }),
    ("metal", {
        "metal", "heavy metal", "death metal", "black metal", "doom metal",
        "thrash metal", "thrash", "extreme metal", "progressive metal",
        "speed metal", "nu metal", "sludge metal",
        "heavymetal", "blackmetal", "deathmetal", "doommetal", "numetal",
        "metalcore", "deathcore",
    }),
    ("punk", {
        "punk", "punk rock", "post-punk", "post punk", "hardcore punk",
        "pop punk", "street punk", "postpunk", "poppunk",
        "skate punk", "psychobilly", "garage punk",
        "proto-punk", "art punk", "d-beat", "crust punk",
        "screamo", "emo", "post-hardcore",
    }),
    ("reggae", {
        "reggae", "dub", "ska", "dancehall", "roots reggae",
        "rocksteady", "ragga", "lovers rock", "conscious reggae",
        "reggae fusion",
    }),
    ("soul", {
        "soul", "soul music", "motown", "funk", "neo soul",
        "neosoul", "neo-soul", "deep soul", "classic soul",
        "psychedelic soul", "disco", "new jack swing",
        "p-funk", "g-funk",
    }),
    ("experimental", {
        "experimental", "noise", "avant-garde", "avantgarde", "avant garde",
        "musique concrete", "electroacoustic", "glitch", "microsound",
        "acousmatic", "sound collage", "harsh noise", "plunderphonics",
        "free improvisation", "free improv", "improvisation",
        "breakcore", "digital hardcore", "circuit bending",
        "generative", "algorithmic composition",
    }),
    ("pop", {
        "pop", "pop music", "indie pop", "dream pop", "chamber pop",
        "baroque pop", "art pop", "electropop", "dance pop",
        "teen pop", "power pop", "twee pop", "indiepop",
        "alternative pop", "k-pop", "kpop", "j-pop", "jpop",
        "dreampop", "synthpop",
    }),
    ("industrial", {
        "industrial", "ebm", "rhythmic noise", "power electronics",
        "industrial music", "industrial noise", "post-industrial",
    }),
]

# Lookup: alias -> canonical
TAG_TO_GENRE = {alias.lower(): canon for canon, aliases in GENRE_MAP for alias in aliases}
CANONICAL    = {canon for canon, _ in GENRE_MAP}


def resolve_genre(raw: str) -> str | None:
    """Map a raw genre string to a canonical genre. Returns None if unmappable."""
    if not raw:
        return None
    low = raw.strip().lower()
    if low in CANONICAL:
        return low
    return TAG_TO_GENRE.get(low)


def resolve_tags(tags_str: str) -> str | None:
    """Scan a comma/semicolon-separated tags string for the first canonical genre hit."""
    if not tags_str:
        return None
    for tok in tags_str.replace(";", ",").replace("|", ",").split(","):
        hit = resolve_genre(tok.strip())
        if hit:
            return hit
    return None
