# CSnap

Simple python script to make large snapshots of code and placing the image in the clipboard for further manipulation. You can use it via editor ([helix](https://helix-editor.com/)), [sf](https://github.com/saltytine/sf) and [PureRef](https://www.pureref.com/).

## Installation

```bash
git clone https://github.com/saltytine/csnap
ln -s $PWD/codesnap/codesnap $HOME/.local/bin/cs
```

## Dependencies

- pypygments
- pango-view
- [ansifilter](https://gitlab.com/saalen/ansifilter)
- xclip

## Bug

Rn when the file is larger than 1500, loc `pango-view` appears to silently crash without producing an image.
