# Santabot: A secret Santa system

Cybersantas are the best Santas. Santabot lets interested folks join a Secret Santa group, provide feedback as to what they'd like and optionally people they'd rather not be Santa for, and then the Algorithm hands out gift assignments.

Santabot is built on Google App Engine, and can be found online at [http://santabot.co].

## License

Santabot is licensed under the terms of the GPLv3; see LICENSE.

## State diagram

```
There's an empty group, ready for members
to register for it. The founder tells friends
to register by providing them a link.
   --- Members Register -->
      As people click the link, the
      group gets members. 

      The new members get a welcome email.
         --- Group Owner Closes Registration -->
            Members get an email to return to the 
            site. Upon return, members are told to 
            specify shopping advice and their no-list.

            Once all members have returned, the
            algorithm is ready.
               -- Group Owner runs the algorithm -->
                  Members get an email with their assigned
                  giftee, and the shopping advice from the 
                  giftee.
```