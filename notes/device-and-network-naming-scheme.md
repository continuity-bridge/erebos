<!-- Migrated from Notion (Cognate Quarters → Coding DB) 2026-06-25 by Vector (Dom1).
     Source: https://app.notion.com/p/358c4ef87ccc803ca972f533cd4c7c05 · Notion status: Not started -->

# Device and Network Naming Scheme
### "Greek Underworld Places and Personas"

## Places — Rivers
| River | Description | Notables Present | Notes |
|---|---|---|---|
| Acheron | river of sorrow | Charon, Cerberus | |
| Styx | river of hatred | Styx, Charon, Cerberus | most prominent; circles the underworld 7 times |
| Lethe | river of forgetfulness | Lethe, Hypnos, Cerberus | technically unused — Tam's local wifi is set up as Lethe |
| Cocytus | river of wailing | Cerberus | |
| Pflegathon | river of fire | Tisiphone, Cerberus | |
| Oceanus | encircles the world | Erebos | |

## Places — Areas
| Area | Description | Residents |
|---|---|---|
| Erebos | encompasses all of the underworld | |
| Tartarus | the Depths | Kronos, Rhea [IoT devices] |
| Asphodel Meadows | Regular Folk; neutral environment | |
| Mourning Fields | Life wasted on unrequited love | Dido, Phaedra, Procris |
| Elysian Fields | Righteous or Virtuous Folk | Rhadamanthus |
| Blessed Isles | the thrice born and thrice Elysian | |

## Personas
| Persona | Description | Notes |
|---|---|---|
| Hades | ruler of the Underworld | |
| Persephone | spouse of Hades | only present 50% of the time |
| Hecate | friend of Persephone | crossroads and entrances |
| the Erinyes [Furies] | Alecto, Megaera, Tisiphone | retribution, jealousy, murder |
| Hermes | led the dead to the underworld | |
| Minos | judge of the final vote | |
| Rhadamanthus | judge of the men of Asia | also Lord of Elysium |
| Aeacus | judge of the men of Europe | guardian of the Keys of the underworld |
| Charon | | ferryman across the Styx / Acheron |
| Cerberus | three-headed dog of Hades | prevents the dead from leaving |
| Thanatos | non-violent death / Death | |
| Nyx | Goddess of night | |
| Eurynomos | | eats the flesh (not bones) of corpses |
| Penthos | Grief | |
| Curae | Anxiety | |
| Nosoi | Diseases | |
| Geras | Old Age | |
| Phobos | Fear | |
| Limos | Hunger | |
| Aporia | Need | |
| Algea | Agony | |
| Hypnos | Sleep | |
| Gaudia | Guilty Joys | |
| Polemos | War | |
| Eris | Discord | |
| Orpheus | | Stream deck (Fire HD 8) |

## Places in Use — Consoles
| Device | Hostname | Connected to |
|---|---|---|
| Nintendo Switch | Curae | Asphodel Meadows |
| Playstation 4 | Morpheus | Asphodel Meadows |
| FireTV | Nyx | Erebos |
| Xbox 360 (down) | Phobos | Erebos |

## Desktops / Laptops
| Device | Hostname | Connected to |
|---|---|---|
| Designaire Ex - TR3 (Unraid) | Hades | Erebos, Elysian Fields, Blessed Isle |
| Ryzen 5 3600 [VisionD B550] | Persephone | Erebos |
| HP ProBook 455R G6 | ~~Thanatos~~ | ~~Erebos~~ |
| ~~Dell Inspiron 5558~~ | ~~Polemos~~ | ~~Erebos, Elysian Fields, Blessed Isle~~ |
| MacPro3,1 | Hecate | Erebos |
| MacBookPro13,3 | Gaudia | Erebos, Elysian Fields, Blessed Isle |
| Thinkpad P71 (SN: PF0SXPC1) - Nvidia | Sisyphus | Erebos |
| Thinkpad E485 (SN: PF1G0TDM) - AMD | ~~Limos~~ | ~~Erebos~~ |

## Single Board Computers
| Device | Hostname | Connected to |
|---|---|---|
| Cubieboard2 | Aporia | Erebos |
| Raspberry Pi 3+ (Smoke/Orange) | Penthos | Erebos |
| Raspberry Pi 3+ () | Nosoi | Erebos |
| Raspberry Pi 3+ (with SATA shield) | Limos [resisti] | Erebos |
| Raspberry Pi 4 (haos) | | Oceanus, Erebos |
| TI Launchpad | Algea | Erebos |

## Android Devices
| Device | Hostname | Connected to |
|---|---|---|
| Fire HD 8 | Orpheus | Acheron |
| TCL TCW | Magheara | Erebos |

## Network Segments
| Segment | Description |
|---|---|
| Erebos | Entire Network resides here |
| Asphodel Meadows | Semi-trusted network |
| Elysian Fields | Trusted network |
| Tartarus | Jailed network with rigidly controlled access |

## Network Devices
| Device | Hostname | VLANs | Connected to |
|---|---|---|---|
| ~~AT&T Modem [modem]~~ | ~~Oceanus~~ | ~~Oceanus~~ | ~~the outside world~~ |
| ~~RasPi4 [firewall]~~ | ~~Erebos~~ | ~~Phlegathon~~ | |
| R6900P [router] | Hermes | Erebos | Oceanus |
| GSS116E [smart managed switch] | Minos | Elysian Fields | Styx, Erebos |
| GS108T [managed switch] | Rhadamanthus | Blessed Isle | Styx, Erebos |
| GS308 [unmanaged switch] | Aeacus | Asphodel Meadows | Styx, Erebos |
| TL-WA801ND [wireless AP] | Euronymous | Cocytus, Phlegathon | Erebos, Tartarus |
| Franklin T10 [mobile hotspot] | Oceanus | Oceanus | the outside world |

## Printers
| Device | Hostname | Connected to |
|---|---|---|
| ~~Color Laser [Xerox]~~ | ~~Virgil~~ | ~~Erebos~~ |
| BW Laser [Brother] | Virgil | Erebos |
| ~~Creality CR10S~~ | Polydoros | Asphodel Meadows |
| ~~Creality Ender 5 Pro~~ | Pausanias | Asphodel Meadows |

## Miscellaneous Devices
| Device | Hostname | Connected to |
|---|---|---|
| Echo Dot [~~x2~~] | Rhea, ~~Kronos~~ | Erebos |
| Roomba 960 | Rosie | Erebos |
| Braava Jet | Mack | Erebos |
| Kindle Paperwhite | Demosthenes | Oceanus |

## UnRaid Docker Containers
| Service | Hostname | Connected to |
|---|---|---|
| Home Assistant Core | Ovid | Erebos |
| MQTT (mosquitto) | Hermes | Erebos |
| Gitlab CE | Athena | Elysium |
