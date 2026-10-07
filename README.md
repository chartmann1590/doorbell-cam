# 🔔 DoorbellCam

**Know who's at your door — instantly, privately, with no monthly fees.**

DoorbellCam is a smart video doorbell you own completely. A small camera by
your front door watches for visitors, recognizes familiar faces, and sends
an alert to your phone and computer the moment someone arrives. Everything
runs inside your home — your video never goes to the cloud, and there is
nothing to subscribe to.

---

## What it does for you

- 👀 **See who's there, live** — open the app or home dashboard for a real-time view from your front door.
- 🔔 **Get a knock on your phone** — instant alerts for visitors, familiar faces, and doorbell rings, with a photo attached.
- 🙂 **Greet people by name** — teach it once with a photo, and it tells you "Alice is at the door."
- 🕘 **Never miss a visitor** — every visit is saved in a tidy history with photos, so you can catch up anytime.
- 🔒 **Private by design** — video and face memories stay on a computer in your home. No accounts, no uploads, no fees.

## What's in the box (what you'll need)

1. **A small doorbell camera** (about the size of a matchbox) by your door.
2. **Your home computer** — it quietly does the watching and remembering. It just needs to stay on and connected to your WiFi.
3. **Your phone** *(optional but recommended)* — for live view and instant alerts around the house.

> No smart-home hub, no subscriptions, no electrician. If you can plug in a
> camera and open a web page, you can run DoorbellCam.

## Getting started (5 minutes)

1. **Plug in the camera** near your front door and power it on.
2. **Start the home base** on your computer — one command, then leave it running.
3. **Open your dashboard** in any browser at `http://localhost:8765` — you'll see your live door view.
4. **Put the app on your phone** — tap **📱 Get the app** at the top of the dashboard to install it. It finds your home base by itself.
5. **Teach it your household** — in the dashboard, open **Faces**, add a name and a clear photo for each person. Done — future alerts use their names.

*Setting it up for someone else, or comfortable with technical guides? See
[docs/TECHNICAL.md](docs/TECHNICAL.md) for the full maker's setup walkthrough.*

## A day with DoorbellCam

| Moment | What happens |
|---|---|
| A visitor walks up | Your phone lights up: *"Person detected"* with a snapshot. |
| A family member arrives | *"Alice is at the door"* — recognized by name. |
| Someone rings the bell | *"Doorbell pressed"* — logged with a photo and time. |
| You missed it all | Open **Alerts** to browse every visit, or **Live** to check right now. |
| Too many (or too few) alerts | Nudge the sliders in **Settings** — no restart needed. |

## Your privacy, in plain English

- 📵 **Nothing leaves your home.** Video is watched and stored on your own computer — not sent to us or anyone else.
- 🗑️ **You're in charge.** Delete any photo or clear the whole history anytime, in one tap.
- 👁️ **No tracking.** There are no ads, no analytics, no accounts.
- 🏠 **Works without internet.** As long as your home WiFi is up, DoorbellCam works — even if your internet is down. (Optional phone alerts away from home need a free secure tunnel — see the technical guide.)

## Questions, answered

**Do I need to pay anything?**
No. There are no subscriptions or cloud fees — ever.

**Does it work when I'm away from home?**
At home, everything works out of the box. To get alerts while you're out,
install a free secure connector (we recommend Tailscale) on your computer
and phone — it takes a few minutes and is covered in the technical guide.

**What if the power goes out?**
Plug everything back in. The camera and home base find each other again on
their own within a minute or so.

**Can it learn my dog / name my kids / ignore the street?**
It recognizes human faces you enroll, and you can tune how sensitive it is
and how often it alerts you in **Settings**. Point the camera at your porch
(not the street) for the calmest experience.

**I see "Camera offline." What do I do?**
Check that the little camera has power and your WiFi is up. It usually
reconnects by itself. Still stuck? The [troubleshooting table](docs/TECHNICAL.md#9-troubleshooting)
walks through fixes in order.

**Where is the nerdy stuff?**
Glad you asked — full setup, configuration, phone-app builds, remote access,
and the complete app reference live here:

- 🔧 [Technical guide](docs/TECHNICAL.md) — installation, settings, troubleshooting
- 🔌 [App reference](docs/API.md) — every feature the app and dashboard can use
- 📱 [Phone app notes](app/README.md) — building and installing the Android app

---

*Built with care for households that want smart-home convenience without
giving up their privacy. Your door, your data.*
