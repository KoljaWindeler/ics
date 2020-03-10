## ICS

Adds a sensor to Home Assistant that displays the date and number of days to the next event. 
E.g. 5 days until the trash will be picked up. The information will be read from a user definded 
ics file.

### Features

- Supports ICS file with reoccuring events
- Events can be filtered, so you can tell it to look only for certain events
- Has an attribute that calculated the number of days, so you can easily run a automation trigger

```yaml
sensor:
  - platform: ics
    name: Packaging
    url: https://www.rmg-gmbh.de/download/Hamb%C3%BChren.ics
    id: 1
```
