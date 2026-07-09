"""
content_generator.py
Full AI pipeline for Stiai Ca?:
  1. GPT-4o-mini picks a topic and writes:
       - title           : 1-3 word heading
       - image_text      : 5-6 sentences that appear ON the image
       - caption         : full post text with hashtags
       - image_prompt    : detailed DALL-E 3 prompt for the background photo
  2. DALL-E 3 generates a beautiful photo matching the curiosity
  3. Both are saved and added to curiosities.json

Usage:
  python content_generator.py              # generate 1 (auto topic)
  python content_generator.py --count 5   # generate 5
  python content_generator.py --topic "Vulturul Plesuv"
  python content_generator.py --list-topics
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

try:
    from openai import OpenAI
except ImportError:
    sys.exit("[content_generator] Run: pip install openai")

BASE_DIR         = Path(__file__).parent
CURIOSITIES_FILE = BASE_DIR / "content" / "curiosities.json"
TOPICS_FILE      = BASE_DIR / "content" / "topics.json"
IMAGES_DIR       = BASE_DIR / "assets" / "images"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

MIN_IMAGE_TEXT_CHARS     = 400
MIN_IMAGE_TEXT_SENTENCES = 5


def count_sentences(text: str) -> int:
    return len([p for p in re.split(r"[.!?…]+", text) if p.strip()])


def image_text_is_short(text: str) -> bool:
    text = (text or "").strip()
    return len(text) < MIN_IMAGE_TEXT_CHARS or count_sentences(text) < MIN_IMAGE_TEXT_SENTENCES


def expand_image_text(title: str, current_text: str, client: OpenAI) -> str:
    """Rewrite short on-image text into 5-6 full sentences."""
    print(f"  [GPT] Expanding image_text for: {title} ...", flush=True)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Rescrie textul pentru imagine despre {title}.\n"
                    f"Text actual (prea scurt): {current_text}\n\n"
                    "Returneaza EXCLUSIV JSON: "
                    '{"image_text": "Exact 5-6 propozitii complete, fiecare 12-20 cuvinte, '
                    "minim 450 caractere, maxim 650. Fapte stiintifice concrete. "
                    'Fara ghilimele interioare."}'
                ),
            },
        ],
        temperature=0.8,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    data = json.loads(resp.choices[0].message.content.strip())
    text = data["image_text"].strip()
    if len(text) > 680:
        text = text[:677] + "..."
    return text

# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "Esti un redactor expert pentru pagina de Facebook Stiai Ca? — o pagina educativa "
    "in limba romana care publica curiozitati despre natura, plante, animale, fenomene "
    "naturale si stiinta. Scrii continut captivant, corect stiintific, usor de inteles "
    "si adaptat publicului general. Tonul este cald, fascinant si informativ. "
    "Nu folosesti niciodata linkuri externe sau referinte la alte site-uri. "
    "IMPORTANT: Nu folosi ghilimele duble in interiorul valorilor JSON."
)

USER_PROMPT_TEMPLATE = (
    "Genereaza o curiozitate pentru pagina Facebook Stiai Ca? despre: {topic}\n\n"
    "Returneaza EXCLUSIV un obiect JSON valid cu exact aceste campuri (fara text in afara JSON-ului):\n\n"
    "{{\n"
    '  "title": "Numele subiectului, 1-3 cuvinte, ex: Margareta",\n'
    '  "image_text": "Exact 5-6 propozitii complete care vor aparea pe imagine. '
    'Fiecare propozitie trebuie sa aiba 12-20 cuvinte. Text detaliat, captivant, '
    'cu fapte stiintifice concrete despre subiect. Minim 450 caractere, maxim 650. '
    'NU scrie doar 2-3 propozitii scurte. Fara ghilimele interioare.",\n'
    '  "caption": "Textul complet al postarii Facebook — un mini-articol educational. '
    'Scrie 8-10 paragrafe, fiecare cu 4-6 propozitii (minim 800 cuvinte total). '
    'Include: introducere captivanta, context istoric/stiintific, fapte detaliate, '
    'exemple concrete din Romania sau lume, de ce conteaza, curiozitati bonus. '
    'La final adauga 8-12 hashtag-uri relevante. Fara ghilimele interioare.",\n'
    '  "image_prompt": "A detailed English prompt for gpt-image-1. The photograph MUST clearly show '
    '{topic} as the main subject — unmistakable, large, and centered in the UPPER HALF of the frame. '
    'The lower third should be simple blurred background (forest floor, sky, or water) for text overlay. '
    'Close-up or medium shot, subject fully visible. Specify: exact subject, environment, lighting. '
    'Do NOT show unrelated animals or objects. '
    'End with: professional nature photography, 4:5 portrait, no text, no watermark."\n'
    "}}"
)


# ── State helpers ─────────────────────────────────────────────────────────────

def load_curiosities() -> list:
    if CURIOSITIES_FILE.exists():
        with open(CURIOSITIES_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return []


def save_curiosities(data: list) -> None:
    with open(CURIOSITIES_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def load_topics() -> list:
    if TOPICS_FILE.exists():
        with open(TOPICS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return []


def make_id(title: str, existing: set) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower().strip())[:30].strip("-")
    n, candidate = 1, f"{base}-001"
    while candidate in existing:
        n += 1
        candidate = f"{base}-{n:03d}"
    return candidate


def pick_topic(topics: list, curiosities: list) -> str:
    used = {c["title"].lower() for c in curiosities}
    unused = [t for t in topics if t.lower() not in used]
    import random
    return random.choice(unused if unused else topics)


# ── Step 1: GPT writes the curiosity ──────────────────────────────────────────

def gpt_generate(topic: str, client: OpenAI) -> dict:
    print(f"  [GPT] Writing curiosity about: {topic} ...", flush=True)

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": USER_PROMPT_TEMPLATE.format(topic=topic)},
        ],
        temperature=0.85,
        max_tokens=2500,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        # Try to salvage by removing problematic inner quotes
        cleaned = re.sub(r'(?<!\\)"(?![,\}\]:\s])', "'", raw)
        data = json.loads(cleaned)

    required = {"title", "image_text", "caption", "image_prompt"}
    missing  = required - data.keys()
    if missing:
        raise ValueError(f"GPT response missing fields: {missing}")

    if image_text_is_short(data["image_text"]):
        raise ValueError(
            f"image_text too short ({len(data['image_text'])} chars, "
            f"{count_sentences(data['image_text'])} sentences)"
        )

    # Safety: trim image_text only if extremely long
    if len(data["image_text"]) > 680:
        data["image_text"] = data["image_text"][:677] + "..."

    return data


# ── Step 2: DALL-E 3 generates the background image ───────────────────────────

def dalle_generate(image_prompt: str, save_path: Path, client: OpenAI) -> str:
    print(f"  [DALL-E] Generating image ...", flush=True)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    resp = client.images.generate(
        model="gpt-image-1",
        prompt=image_prompt,
        size="1024x1536",   # Portrait — closest to our 4:5 target
        quality="medium",
        n=1,
    )

    import base64
    # gpt-image-1 returns base64 by default
    b64 = resp.data[0].b64_json
    if b64:
        img_data = base64.b64decode(b64)
    else:
        image_url = resp.data[0].url
        img_data  = requests.get(image_url, timeout=60).content
    save_path.write_bytes(img_data)
    print(f"  [DALL-E] Saved to {save_path.name} ({len(img_data)//1024} KB)")
    return str(save_path)


# ── Full pipeline ─────────────────────────────────────────────────────────────

def generate_curiosities(count: int = 1, topic: str = None) -> list:
    """
    Generate *count* curiosities (text + DALL-E image) and append to curiosities.json.
    Returns the list of newly added entries.
    """
    if not OPENAI_API_KEY:
        sys.exit(
            "[content_generator] OPENAI_API_KEY not set in .env\n"
            "Get a key at https://platform.openai.com/api-keys"
        )

    client      = OpenAI(api_key=OPENAI_API_KEY)
    topics      = load_topics()
    curiosities = load_curiosities()
    existing    = {c["id"] for c in curiosities}
    new_entries = []

    for i in range(count):
        chosen = topic if topic else pick_topic(topics, curiosities + new_entries)
        print(f"\n[{i+1}/{count}] Topic: {chosen}")

        for attempt in range(3):
            try:
                # Step 1: GPT writes text
                gpt_data = gpt_generate(chosen, client)

                # Step 2: DALL-E generates image
                entry_id   = make_id(gpt_data["title"], existing | {e["id"] for e in new_entries})
                image_name = f"{entry_id}.jpg"
                image_path = IMAGES_DIR / image_name

                dalle_generate(gpt_data["image_prompt"], image_path, client)

                # Build entry
                entry = {
                    "id":           entry_id,
                    "title":        gpt_data["title"],
                    "image_text":   gpt_data["image_text"],
                    "caption":      gpt_data["caption"],
                    "image_prompt": gpt_data["image_prompt"],
                    "image_file":   image_name,
                    "posted":       False,
                }
                new_entries.append(entry)
                print(f"  [OK] {entry['title']} — image: {image_name}")
                break

            except Exception as exc:
                print(f"  [Attempt {attempt+1}/3 failed] {exc}")
                if attempt < 2:
                    time.sleep(3)
        else:
            print(f"  [SKIP] Could not generate for topic: {chosen}")

        # Pause between generations to respect rate limits
        if i < count - 1:
            time.sleep(2)

    if new_entries:
        curiosities.extend(new_entries)
        save_curiosities(curiosities)
        n = len(new_entries)
        print(f"\n[content_generator] Added {n} new entr{'y' if n==1 else 'ies'} to curiosities.json")

    return new_entries


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI content + image generator for Stiai Ca?")
    parser.add_argument("--count",       type=int, default=1,    help="How many to generate")
    parser.add_argument("--topic",       type=str, default=None, help="Specific topic")
    parser.add_argument("--list-topics", action="store_true",    help="Print all topics and exit")
    args = parser.parse_args()

    if args.list_topics:
        for t in load_topics():
            print(f"  - {t}")
        return

    generate_curiosities(count=args.count, topic=args.topic)


if __name__ == "__main__":
    main()
