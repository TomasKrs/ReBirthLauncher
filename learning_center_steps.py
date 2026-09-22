# Tips And Tricks + a short How-To-Start path for ReBirth RB-338 / ToolBox.
# Paraphrased from common workflow practice and Getting Started with ReBirth 2.0.
# Original wording only — not a copy of any PDF.

REBIRTH_TUTORIAL_STEPS = [
    # ---------- How to start ----------
    {
        "id": "howto_welcome",
        "title": "How to Start — 1. What you need",
        "summary": "Light tutorial: tools before first notes.",
        "body": (
            "You need three pieces working together:\n\n"
            "1. ReBirth RB-338 installed (Get ReBirth / Start tab).\n"
            "2. The CD image mounted when ReBirth asks for the disc (ToolBox does this on launch).\n"
            "3. A silent / blank song so you are not fighting the demo loop.\n\n"
            "ToolBox keeps Mods, Songs, Documents, and Inspire Me in one place. Finish install first, "
            "then come back to this Tips And Tricks tab for practice ideas."
        ),
        "action": "downloads",
        "action_label": "Get ReBirth",
    },
    {
        "id": "howto_audio",
        "title": "How to Start — 2. Fix audio first",
        "summary": "Driver and buffer before creativity.",
        "body": (
            "Open ReBirth → Preferences and pick a real sound-card driver (avoid generic / emulated names).\n\n"
            "Load any song, press Play, open Preferences again, and nudge the playback performance / buffer "
            "until crackles disappear. DirectX usually needs a shorter buffer than MME.\n\n"
            "If audio is wrong, every filter tweak will feel broken — lock this in once, then ignore it."
        ),
        "action": "launch",
        "action_label": "Open Start",
    },
    {
        "id": "howto_silent",
        "title": "How to Start — 3. Silent Default Song",
        "summary": "Empty rack, Save As immediately.",
        "body": (
            "Close the annoying default demo. File → Open Song → leave Demo Songs → Default Songs → "
            "Silent Default Song.rbs.\n\n"
            "Press Play — silence is correct. File → Save As right away (e.g. my_first.rbs) so you never "
            "overwrite the template.\n\n"
            "From ToolBox RBM DB you can also double-click a mod screenshot to launch an empty project "
            "with that skin already selected."
        ),
        "action": "mods",
        "action_label": "RBM DB",
    },
    {
        "id": "howto_modes",
        "title": "How to Start — 4. Pattern vs Song mode",
        "summary": "Compose first, arrange second.",
        "body": (
            "Pattern Mode loops one pattern while you program steps and twist knobs — nothing is recorded "
            "to a timeline.\n\n"
            "Song Mode records pattern changes and knob moves over bars. Always fill Pattern Mode banks "
            "before you press Record in Song Mode.\n\n"
            "Rule of thumb: 80% of your time early on is Pattern Mode."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "howto_first_303",
        "title": "How to Start — 5. First 303 line",
        "summary": "Enable steps, pick pitches, add accent/slide.",
        "body": (
            "Select TB-303 #1. Enable step 1 with note/silence, pick a key, then STEP to 3, 5, 8…\n\n"
            "Strong beats sit on 1, 5, 9, 13. Add Accent on downbeats and Slide into the next note for "
            "classic acid glides.\n\n"
            "Turn Resonance up a bit, then sweep Cutoff while Play runs — that interaction is the sound. "
            "Edit → Randomize Pattern is fine as a sketch; rewrite steps afterward."
        ),
        "action": "inspire",
        "action_label": "Inspire Me 303",
    },
    {
        "id": "howto_first_drums",
        "title": "How to Start — 6. First drum pattern",
        "summary": "Kick / snare / hats in sixteen steps.",
        "body": (
            "On TR-808 or TR-909: select BD, light 1-5-9-13. Add SD on 5 and 13 (or 7/10/15 for swing). "
            "Add closed hats on odd steps.\n\n"
            "909 steps cycle empty → soft → loud. Double-click kicks for punch.\n\n"
            "Copy the pattern to A2, then strip kicks from A1 so Song Mode can flip between light and full "
            "beats."
        ),
        "action": "inspire",
        "action_label": "Drum grids",
    },
    {
        "id": "howto_record",
        "title": "How to Start — 7. Record a tiny song",
        "summary": "Initialize from Pattern Mode, then overdub.",
        "body": (
            "Set mixer faders and filter knobs to starting positions in Pattern Mode. Save.\n\n"
            "Switch to Song Mode → Edit → Initialize Song From Pattern Mode. BAR = 1 → Record → Play.\n\n"
            "Fade drums in, change pattern from A1 to A2, ride Cutoff. Stop, set Loop Length to your last "
            "bar, rewind, listen. Record again to overdub — previous moves stay.\n\n"
            "File → Export Loop as Audio File when you want a WAV/AIFF."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "howto_toolbox",
        "title": "How to Start — 8. ToolBox shortcuts",
        "summary": "Mods, Inspire Me, library, backup.",
        "body": (
            "RBM DB — pick skins, pin favorites, import .rmb/.rbm into Mods/.\n"
            "Inspire Me — sketch banks offline, Load/Save Song, Launch in ReBirth.\n"
            "Song Library — search BPM / mod / favorites.\n"
            "Settings — maximize on launch, CPU affinity, Backup Collection (7z).\n\n"
            "The rest of this tab is Tips And Tricks — jump around, mark done, revisit often."
        ),
        "action": "inspire",
        "action_label": "Inspire Me",
    },
    # ---------- Tips And Tricks ----------
    {
        "id": "tip_save_as",
        "title": "Tip — Version your songs",
        "summary": "Save As every major change.",
        "body": (
            "Keep Silent Default Song untouched. Name versions by idea: acid_intro_v1.rbs, acid_intro_v2.rbs.\n\n"
            "Before destructive Edit → Randomize / Alter Pattern, Save As. Patterns are cheap to regenerate; "
            "happy accidents are expensive to lose."
        ),
        "action": "library",
        "action_label": "Song Library",
    },
    {
        "id": "tip_banks",
        "title": "Tip — Banks as song sections",
        "summary": "A = groove, B = break, C = fill…",
        "body": (
            "Treat banks as arrangement chapters: Bank A = main groove, B = breakdown, C = fills, D = ending.\n\n"
            "In Song Mode you only flip pattern numbers — the hard work is already in the banks. Fill eight "
            "slots per bank so you can move without editing mid-take."
        ),
        "action": "inspire",
        "action_label": "Pattern selector",
    },
    {
        "id": "tip_copy_paste",
        "title": "Tip — Copy / Paste / Alter",
        "summary": "Build variations without rewriting.",
        "body": (
            "Edit → Copy Pattern on 303 #1, Paste on 303 #2, drop Tune for a bass layer, then Alter Pattern "
            "once so they are not clones.\n\n"
            "In ToolBox Inspire Me the right-hand Copy panel mirrors this: copy selected modules from one "
            "slot to another with checkboxes for #1 / #2 / drums."
        ),
        "action": "inspire",
        "action_label": "Copy panel",
    },
    {
        "id": "tip_reso_cutoff",
        "title": "Tip — Cutoff needs Resonance",
        "summary": "They work as a pair.",
        "body": (
            "Cutoff sweeps are dull when Resonance is near zero. Raise Reso first, then move Cutoff — that "
            "is the acid whistle.\n\n"
            "Env. Mod + Decay control how the filter opens after each note. Short Decay + high Reso = "
            "percussive blips; long Decay = singing tails."
        ),
        "action": "inspire",
        "action_label": "303 tab",
    },
    {
        "id": "tip_slide_accent",
        "title": "Tip — Accent and Slide placement",
        "summary": "Rhythm of emphasis, not just pitch.",
        "body": (
            "Accent on off-beats makes the line push forward. Slide into notes that land on 1 or 5 for "
            "classic glides.\n\n"
            "Too many slides muddy the groove; try slides only every 2–4 notes. Accents every 4 steps is "
            "a safe starting grid."
        ),
        "action": "inspire",
        "action_label": "Piano roll",
    },
    {
        "id": "tip_octaves",
        "title": "Tip — Two 303s, two octaves",
        "summary": "Lead high, bass low.",
        "body": (
            "Park 303 #1 Tune toward the top and 303 #2 toward the bottom. Same (or related) pattern in "
            "both octaves densifies the track without a third instrument.\n\n"
            "Mute one mixer channel while writing so you hear decisions clearly, then blend with faders."
        ),
        "action": "inspire",
        "action_label": "Mini mixer",
    },
    {
        "id": "tip_shuffle",
        "title": "Tip — Shuffle is a spice",
        "summary": "Small amounts first.",
        "body": (
            "Global Shuffle Amount plus per-section shuffle switches route swing where you want it.\n\n"
            "Start low. Extreme shuffle on dense 16th hats feels drunk; on sparse 303 lines it can feel "
            "human. Toggle shuffle off when checking if a pattern is actually interesting."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_808_vs_909",
        "title": "Tip — 808 soft / 909 hard",
        "summary": "Pick the character for the genre.",
        "body": (
            "808 is rounder and roomier — great under atmospheric acid. 909 is sharper for house / techno "
            "backbones.\n\n"
            "You can program both machines and mute one mixer channel, or switch focus in Song Mode. "
            "Inspire Me keeps separate 808 and 909 stores so you can preview either."
        ),
        "action": "inspire",
        "action_label": "808 / 909",
    },
    {
        "id": "tip_hat_rules",
        "title": "Tip — Open vs closed hats",
        "summary": "They fight for the same space.",
        "body": (
            "Open hats often choke closed hats on the same step depending on the machine/mod. Prefer OH "
            "on off-beats and CH on the grid, or leave holes so opens can breathe.\n\n"
            "Accent layer on hats is subtle but sells the groove — accent 1 and 9 only if unsure."
        ),
        "action": "inspire",
        "action_label": "Hat rows",
    },
    {
        "id": "tip_mix_before_fx",
        "title": "Tip — Mix before effects",
        "summary": "Balance dry, then dirt.",
        "body": (
            "Set instrument faders so drums and 303s sit together dry. Then enable Dist / PCF / Delay sends "
            "per channel.\n\n"
            "Huge distortion on an already-hot 303 will bury the kick. Pull the 303 fader down before you "
            "crank Dist Amount."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_pcf",
        "title": "Tip — PCF as a rhythmic filter",
        "summary": "Pattern-driven movement.",
        "body": (
            "PCF uses selectable motion patterns (0–54) to automate a filter on sent channels. Try LP for "
            "303-style sweeps, BP for narrower vocal-ish filters.\n\n"
            "Amount and Decay decide how dramatic each hit is. Route only drums or only 303s first so you "
            "hear what PCF is doing."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_delay",
        "title": "Tip — Delay feedback caution",
        "summary": "Echoes can runaway.",
        "body": (
            "Delay Steps + Straight/Triplet set the rhythm of repeats. Feedback returns output to input — "
            "high values can howl forever.\n\n"
            "Pan the delay slightly opposite the dry signal for width. Short delay on hats = groove glue; "
            "long delay on sparse 303 notes = dub space."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_comp",
        "title": "Tip — Compressor for punch",
        "summary": "Threshold above the quiet parts.",
        "body": (
            "Compressor ratio and threshold keep peaks in check and can make a mix feel louder without "
            "clipping. Watch the reduction meter — constant full-scale pumping means Threshold is too low.\n\n"
            "Master Comp affects everything; per-channel Comp only hits routed instruments."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_song_init",
        "title": "Tip — Initialize Song from Pattern",
        "summary": "Reset timeline, keep patterns.",
        "body": (
            "Edit → Initialize Song From Pattern Mode copies current Pattern Mode settings into Song Mode "
            "and clears previous automation.\n\n"
            "Use it when a take went wrong but the patterns are good. Do not confuse it with wiping Pattern "
            "banks — those stay until you clear or overwrite them."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_overdub",
        "title": "Tip — Overdub instead of redoing",
        "summary": "Second pass adds, does not erase.",
        "body": (
            "After the first Record pass, rewind to bar 1 and Record again. New pattern flips and knob "
            "moves stack on top.\n\n"
            "Plan passes: (1) fader arrangement, (2) pattern changes, (3) filter performances. Easier than "
            "one heroic take."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_loop_export",
        "title": "Tip — Loop points before export",
        "summary": "Export exactly what you hear.",
        "body": (
            "Set Start and Length under Loop to cover the song, enable Loop, audition once, then "
            "File → Export Loop as Audio File.\n\n"
            "If Length is short, the WAV cuts early. If Start is wrong, you miss the intro. Keep the .rbs "
            "master even after export."
        ),
        "action": "library",
        "action_label": "Song Library",
    },
    {
        "id": "tip_mods_learn_default",
        "title": "Tip — Learn default before exotic mods",
        "summary": "Skins rename the same controls.",
        "body": (
            "Mods change graphics and sometimes samples. The logic (banks, pattern mode, mixers) stays "
            "familiar — labels may not.\n\n"
            "Build muscle memory on Standard ReBirth, then explore RBM DB. Pin favorites with ★ and use "
            "Recent filter when hunting skins you already tried."
        ),
        "action": "mods",
        "action_label": "RBM DB",
    },
    {
        "id": "tip_mod_songs",
        "title": "Tip — Songs remember their mod",
        "summary": "Launch with the matching skin.",
        "body": (
            "Each .rbs can reference a mod name. ToolBox Song Library and RBM DB show which library songs "
            "use a skin.\n\n"
            "Launching from RBM DB prepares the mod in ReBirth's Mods folder when needed. If a song opens "
            "with the wrong look, check the mod file is installed."
        ),
        "action": "mods",
        "action_label": "RBM DB",
    },
    {
        "id": "tip_inspire_workflow",
        "title": "Tip — Inspire Me as a sketchpad",
        "summary": "Generate, edit, Save Song, launch.",
        "body": (
            "Randomize a bank, edit the piano roll / drum grid, preview with Loop Mix and the mini mixer.\n\n"
            "Clear Bank / Clear All Patterns affect only the visible instrument. Clear All Banks from All "
            "Instruments wipes everything.\n\n"
            "Save Song writes an .rbs; Launch in ReBirth sends a temp song for audition."
        ),
        "action": "inspire",
        "action_label": "Inspire Me",
    },
    {
        "id": "tip_density",
        "title": "Tip — Density vs space",
        "summary": "Empty steps are musical.",
        "body": (
            "Full 16-step 303 lines with max density sound busy fast. Leave rests — silence makes accents "
            "hit harder.\n\n"
            "Same for drums: remove every other hat for half-time feels. Inspire Me Note Density is a "
            "generator bias, not a law — delete notes by hand."
        ),
        "action": "inspire",
        "action_label": "Density slider",
    },
    {
        "id": "tip_pattern_length",
        "title": "Tip — Shorter than 16 steps",
        "summary": "Steps control can change phrase length.",
        "body": (
            "Not every idea needs 16 steps. Shorter patterns repeat faster and can feel like fills or "
            "stutters when automated in Song Mode.\n\n"
            "When switching length, re-check accents — a pattern that worked at 16 may feel cramped at 12."
        ),
        "action": "launch",
        "action_label": "Launch ReBirth",
    },
    {
        "id": "tip_mute_solo",
        "title": "Tip — Mute while arranging",
        "summary": "Hear one idea at a time.",
        "body": (
            "Mixer on/off (or ToolBox mix mutes) lets you judge a bassline without hats screaming. Solo "
            "mentally: mute everything except the part you are editing, then unmute for context.\n\n"
            "In Song Mode, mute automation can be recorded too — useful for dropouts."
        ),
        "action": "inspire",
        "action_label": "Mix mute",
    },
    {
        "id": "tip_cpu_maximize",
        "title": "Tip — ToolBox launch options",
        "summary": "Maximize, CPU lock, resolution.",
        "body": (
            "Settings → Maximize ReBirth window on launch keeps re-applying maximize while the app "
            "settles (old Win32 apps often reset size after load).\n\n"
            "CPU affinity / resolution tweaks help on modern Windows. If maximize still fails, launch once "
            "manually maximized, then retry — some skins open a different first window."
        ),
        "action": "launch",
        "action_label": "Settings",
    },
    {
        "id": "tip_backup",
        "title": "Tip — Backup Collection (7z)",
        "summary": "Archive Mods + Songs + Documents.",
        "body": (
            "Settings → Backup Collection packs your ToolBox folders with 7z. Run it before big mod imports "
            "or experiments.\n\n"
            "Also copy rebirth_manual.pdf and getting-started PDFs into Documents/ for one-click access."
        ),
        "action": "documents",
        "action_label": "Documents",
    },
    {
        "id": "tip_midi",
        "title": "Tip — MIDI control later",
        "summary": "Knobs from hardware.",
        "body": (
            "Once the mouse workflow is comfortable, map a MIDI controller. ReBirth supports remote control "
            "and quick learning of assignments.\n\n"
            "External sync is for locking tempo to hardware sequencers — tackle it after Song Mode feels "
            "natural. See the full PDF manual for mapping tables."
        ),
        "action": "documents",
        "action_label": "Documents",
    },
    {
        "id": "tip_finish",
        "title": "Tip — Finish small tracks",
        "summary": "Ship 32–64 bars often.",
        "body": (
            "A finished 64-bar loop teaches more than a perfect unfinished epic. Export, listen away from "
            "the rack, note three fixes, open v2.\n\n"
            "Mark tips done in this list as you try them. Revisit How to Start when you onboard a friend — "
            "or yourself after a break."
        ),
        "action": "library",
        "action_label": "Song Library",
    },
]
