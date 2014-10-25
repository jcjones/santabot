import random, logging, itertools

class PeopleMatcher(object):
  def __init__(self):
    self.data=[]
    self.honoredProhibited = 0

  def __repr__(self):
    return str(self.data)

  def setHonoredProhibited(self, val):
    self.honoredProhibited = int(val)

  def addPerson(self, person, prohibited=[]):
    for o in prohibited:
      if person == o:
        raise Exception("Person prohibited self")

    logging.error("Prohi i22 {}".format(prohibited))
    random.shuffle(prohibited)
    logging.error("Prohi is {}".format(prohibited))

    self.data.append({"id":person, "prohibited":prohibited})

  def execute(self):
    sources = list(self.data)
    
    stillTrying = True
    tryNumber = 0
    graphSegments = None

    while stillTrying and tryNumber < 99:
      tryNumber = tryNumber+1
      targets = list(sources)
      random.shuffle(targets)
      graphSegments = []


      # Assume we're done
      stillTrying = False

      for i in range(len(sources)):
        # logging.info("{} == {}".format(sources[i]["id"], targets[i]["id"]))

        # Don't assign to self
        if sources[i]["id"] == targets[i]["id"]:
          # logging.info("Failed self")
          stillTrying = True
          break

        # Don't assign to prohibited person
        if targets[i]["id"] in sources[i]["prohibited"][:self.honoredProhibited]:
          # logging.info("Failed right prohibs left")
          stillTrying = True
          break

        # Note the assignment
        graphSegments.append({
          "source": sources[i]["id"],
          "target": targets[i]["id"]
        })

    if stillTrying:
      # We couldn't solve in 99 tries
      return None

    return graphSegments