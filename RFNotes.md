# RF Notes

Mask idea is good, but we need to revisit a couple of things

1. Last real session we had concluded we're sending the wrong type of signal;should that be fixed first?
2. There is an implicit assumption we got the id for each of the fans exactly
right. If we had wouldn't the light command work for both? Realize it could be a signal strength issue, but worth questioning

I think the masking idea and using the Mac to do the heavy lifting makes sense

- along with the command, pass the start and stop
- firmware maybe validates numbers are >=0 and the second is > first

## Questions

1. Is there a logical extension of the masking concept where we pass the raw
bytes of what we want the radio to play? Reviewing your last note, it seems like this may be where you ended up as well.
2. Should we have multiple versions of the firmware in separate folders and
/firmware becomes a symbolic link to point to the current one? Would probably
cause VSCode all sorts of confusion, but . . .
