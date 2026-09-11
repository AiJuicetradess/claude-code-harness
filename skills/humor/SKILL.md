---
name: humor
description: Write, punch up, evaluate, or de-AI humor — jokes, taglines, captions, hooks, lyrics, ad copy, social posts, brand/trader/founder voice. Trigger on "funny", "witty", "punchy", "dry", "make it land", "punch this up", "is this funny", "less AI-sounding", or comedic copy in humor-load-bearing genres (calypso, soca, hip-hop, country, real-estate-with-personality). Default ON when in doubt.
---

# Humor

A skill for writing and evaluating humor without sounding like an AI doing a bit.

## The core problem

Almost everything an LLM writes that's "supposed to be funny" fails in the same handful of ways: it announces itself, it hedges, it stays safe, it explains itself, and it sounds like every other LLM doing the same bit. This skill exists to name those failure modes, suppress them, and apply the actual mechanics that make humor work.

If you can't articulate *why* something is funny, you can't reliably write something funny. Vibes are not enough.

## Foundational principles

**Specificity is the single biggest lever.** "A chair" is dead. "A 1987 La-Z-Boy with a cigarette burn on the left arm" might live. Generic = unfunny. Pull the camera in until you can see lint on the surface.

**Commitment beats hedging.** "It's kind of like..." "I guess you could say..." "almost as if..." — these are the sounds of a joke being killed before it's told. Either commit to the premise or cut the line.

**Surprise must be earned, not announced.** The setup teaches the audience an assumption; the punchline breaks one specific load-bearing word inside that assumption. "Comedically speaking," "in a humorous way," and "if you'll permit a joke" are confessions that the joke isn't going to work.

**Truth is the engine.** The laugh comes from recognition — "oh god, that *is* what it's like." A joke that isn't true about something can be clever; it can't be funny.

**Cut, then cut again.** Every word that isn't the setup, the load-bearing pivot, or the payoff is drag. Comedy lives in economy.

**Voice matters more than material.** The same line can land or die depending on who's saying it. Before generating, fix the speaker in mind: who, with what relationship to the subject, with what stake in the outcome.

## Workflow

Pick the lane that matches the request.

### Generating humor from scratch
1. **Find the truth.** What's genuinely weird, frustrating, hypocritical, or absurd about the subject? Write three honest observations before writing any jokes.
2. **Pick a comedic move** (see Toolkit). Don't reach for wordplay first; it's the easy mode that signals AI.
3. **Get specific.** Replace every general noun with a concrete one. Replace every adjective with a thing.
4. **Run the critic pass** (see Failure Modes and Critic Checklist).
5. **Cut 30%.** If the joke survives, keep cutting until it stops surviving.

### Punching up existing dry copy
1. **Diagnose the voice.** Whose voice is this supposed to be? What's their relationship to the reader? What register — dry/warm/sharp/absurd/mean?
2. **Find the seams.** Where in the copy is there a true observation the writer flinched away from? That's the joke spot.
3. **Add specificity before adding jokes.** Often "make this funnier" is actually "make this more specific."
4. **Don't tax every paragraph.** One sharp moment per paragraph beats four mediocre ones. Comedy density matters.

### Evaluating "is this funny"
Run the Critic Checklist. Be honest. Explain *why* something does or doesn't work, citing the specific mechanic. Vague feedback ("it feels off") is a failure — name the move that's broken.

### Stripping AI-humor tells
Apply the Failure Modes list as an editor — every match is a candidate for cut or rewrite. This pairs with (but is distinct from) general AI-tell removal; this layer targets attempted-humor specifically.

## The toolkit (comedic moves)

Don't default to one. Pick the move that fits the truth being expressed.

- **Misdirection** — setup aims the audience one direction, punchline lands somewhere unrelated but inevitable. "I'm not saying I'm bad with money — I'm saying my bank statement reads like a memoir."
- **Broken assumption (who/what/when/where/how shift)** — setup builds an assumption; punchline reveals one specific element was different than assumed. Specify which element shifts and let it do the work.
- **Specificity escalation** — establish a normal thing, push the specificity past the breaking point. "He's the kind of guy who tips 18% even at a Sbarro."
- **Rule of three** — pattern, pattern, break. The third item subverts. The trick: the third item must be both surprising and obviously true in retrospect.
- **Act-out** — drop into character voice. Best when there's an actual character with stakes (a landlord, an HOA, a desk boss), not a generic "imagine if X said Y."
- **Callback** — reference earlier material. Buys laughs through familiarity. Especially strong in long-form (lyrics, ad campaigns, threads).
- **Self-implication** — narrator pays for the joke. Self-deprecation, but specific. The opposite of safe.
- **Wordplay** — use sparingly. More than one pun within ~200 words signals trying-too-hard.
- **Dry understatement** — true thing said flat, with the absurdity left for the reader to notice. Works when the subject is already loud (real estate, finance, politics, weather).

## Failure modes (the AI-humor tells)

Flag and rewrite any of these:

- **Comedy preamble** — "you ever notice...," "isn't it funny how...," "comedically speaking" — the joke announcing itself.
- **Explaining the joke** — anything after the punchline that clarifies what was funny.
- **Safe targets** — Mondays, Mercury retrograde, "millennials," coffee dependence, Comic Sans. Boring because everyone agrees. Real comedy has stakes.
- **Smug-observer voice** — sounding like an essay that thinks it's a stand-up set. Cadence of "have you ever stopped to consider..."
- **Comedy-cadence overload** — too many em-dashes, beat-rhythm sentence patterns, ironic Capitalization (The Audacity™). Once or twice is a flourish; four times in a paragraph is a tell.
- **Premise without payoff** — "Wouldn't it be weird if..." stated as if the premise itself is the joke. It isn't.
- **Hedge words** — "kind of," "sort of," "almost," "basically." Cut.
- **The wink** — explicit signals this is the funny part: "(see what I did there?)", "...if you know, you know," emoji laugh-tracks, multiple exclamation points.
- **The dad-joke default** — pun-based, surface-level, audience-of-no-one. Acceptable as one beat inside a varied set; lethal as the dominant register.
- **Generic-comedian voice** — sounding like every podcast guest's bit instead of like a specific person with a specific relationship to the topic.
- **Joke density inflation** — four jokes where one would land harder. Cut to the strongest, kill the rest.
- **Reach-for-pop-culture** — leaning on references (Marvel, Star Wars, "literally me," meme phrases) instead of generating the observation. Borrowed laughs decay fast.

## Voice calibration

Before generating, fix four parameters. Don't move forward until they're answered.

1. **Speaker** — Who is talking? (Brand persona, character, narrator with what biases?)
2. **Stake** — What does the speaker stand to gain or lose? Humor without stakes is observational and dead.
3. **Register** — Dry / warm / sharp / absurd / mean. (These are different. Don't blur.)
4. **Audience proximity** — In-group (uses inside terms, assumes knowledge) vs out-group (translates, contextualizes)?

For genre-specific calibration — calypso/soca lyric wit, hip-hop punchline mechanics, trader/finance dry humor, real-estate-with-personality, B2B SaaS one-liners, direct-response cheek — see `references/registers.md`.

## Critic checklist

Before releasing any humor output, walk every item. If you can't honestly check it, revise.

- [ ] Is there a specific load-bearing surprise, or just a topic switch?
- [ ] If the setup is deleted, does the punchline still imply the setup? (If yes, telegraphed — fix.)
- [ ] Is the specificity load-bearing or decorative? (Cut decorative.)
- [ ] Could anyone deliver this line, or does it require this speaker? (Generic = weaker.)
- [ ] Am I explaining the joke anywhere in the surrounding sentences?
- [ ] Is there a real target, or am I being safe?
- [ ] Cut test: can I remove 30% of the words without losing the laugh?
- [ ] Read-aloud test: does it sound like writing-pretending-to-be-speech, or like actual speech?
- [ ] Density test: more than one joke per ~100 words of running prose? (Probably too many.)
- [ ] AI-tell scan: any items from Failure Modes triggered?

## Examples (with diagnostic notes)

### Bad → good

**Bad:** "Buying real estate in the Dominican Republic is amazing — beach, sun, and your money goes so much further! 🏝️☀️"
*Diagnosis: no specificity, no truth, no surprise, emoji wink, generic enthusiasm. Sells nothing because it describes nothing.*

**Better:** "In Vancouver, $200,000 buys you a parking spot. In Las Terrenas, it buys you the parking spot, the car, the condo above it, and a guy named Miguel who will fix anything in your house for the price of a sandwich."
*Why it works: specific contrast, real character (Miguel), the joke pays for the premise rather than announcing it, dry delivery, in-group warmth.*

---

**Bad:** "Trading is wild — sometimes you win, sometimes you learn! 📈"
*Diagnosis: cliché, hedge, emoji wink, comedy-preamble in spirit, no truth.*

**Better:** "My stop loss has been hit so many times this week it's started leaving voicemails."
*Why it works: specific instrument (stop loss, not "the market"), commits to the conceit (voicemails), self-implicating, no explanation.*

---

**Bad:** "She's, like, kind of a mess — but in a charming way, you know?"
*Diagnosis: every hedge word in one sentence, audience flattery ("you know"), generic.*

**Better:** "She owns four label makers and has never labeled anything."
*Why it works: specific (four, label makers), shows rather than tells, leaves the conclusion to the reader.*

## When NOT to be funny

Humor is not always the answer. Suppress it when:
- The subject is grief, illness, fresh trauma, or active crisis.
- The audience is in transactional decision-mode (terms of service, security warnings, fee disclosures).
- The brand voice is explicitly grave (legal, medical, condolences, regulatory).
- A funny line would undercut a credibility move the surrounding prose is doing.

Flag this back to the user rather than refusing — they may want the line anyway, with awareness of the trade.

## Companion files (optional, build as needed)

- `references/registers.md` — Genre-specific comedic conventions (calypso/soca, hip-hop, country, finance dry, real estate, B2B). Fill from your own voice work; don't pre-fabricate.
- `references/great-lines.md` — A small, hand-curated collection of lines that worked, with one-sentence diagnoses of *why*. Useful as a few-shot reference when generating in a specific register. Keep small (~20 entries); large reference files dilute.
