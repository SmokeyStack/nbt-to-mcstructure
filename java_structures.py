from time import time
import json
from pynbt import NBTFile, TAG_Compound,TAG_Int, TAG_List, TAG_String
from progress_bar import track

blocksj2b = json.loads(open('./blocksJ2B.json', 'r').read())
data = { 'blockstates': {} }
MC_VERSION = "1.19.70.02"

def getVersion (versionString: str) -> int:
  def getHex (n):
    output = hex(int(n))[2:]
    if len(output) < 2:
      output = '0' + output
    return output
  
  version = versionString.split('.')
  return eval(f"0x{''.join(map(getHex, version))}")

def getStructureBlockIndex(distY, distZ, x, y, z):
  return ((distY * distZ) * x) + ((distZ) * y) + z

def getDynamicBlockIdentifier(blockobject):
  baseidentifier = "minecraft:air"
  stateslist = {
    # {name: 'direction', value: '0'}
  }
  
  if "name" in blockobject:
    # Bedrock palette object
    baseidentifier = blockobject['name'].value
    for statename in blockobject['states'].value:
      state = blockobject['states'].value[statename]
      stateslist[statename] = state.value

  elif "Name" in blockobject:
    # Java palette object
    baseidentifier = blockobject['Name'].value
    if "Properties" in blockobject:
      for statename in blockobject['Properties'].value:
        state = blockobject['Properties'].value[statename]
        stateslist[statename] = state.value

  else: # Unrecognizable palette object.
    return
  
  # Create dynamic properties list
  properties = []
  for statename in sorted(stateslist):
    properties.append(statename + "=" + stateslist[statename])
  
  return baseidentifier + "["+ ",".join(properties) +"]"

def getBlockObject(dynamicblockid: str, format = 'bedrock'):
  baseidentifier = dynamicblockid.split("[")[0]
  properties = dynamicblockid.split("[")[1].replace("]", "")
  if properties.split(",")[0] != '':
    properties = properties.split(",")
  else:
    properties = []
  
  stateslist = {}
  for property in properties:
    stateslist[property.split("=")[0]] = property.split("=")[1]
  
  if format == "java":
    object = {
      "Properties": TAG_Compound({}),
      "Name": TAG_String(baseidentifier)
    }
    for statename in stateslist:
      object['Properties'].value[statename] = TAG_String(stateslist[statename])

    if len(object['Properties'].value) == 0:
      object.pop('Properties')
    
    return object
  else:
    object = {
      "name": TAG_String(baseidentifier),
      "states": TAG_Compound({}),
      "version": TAG_Int(getVersion(MC_VERSION))
    }
    
    for statename in stateslist:
      # Find bedrock edition state type
      statetype = 'string'
      statevalue = stateslist[statename]
      if statename in data['blockstates']:
        statetype = data["blockstates"][statename].type
        if statetype == 'int':
          statevalue = float(statevalue)
      
      if statetype == 'string':
        object["states"].value[statename] = TAG_String(statevalue)
      else:
        raise f"State type {statetype} not implemented"
    
    return object

def javaToBedrock(structure: NBTFile):
  blocks: TAG_List = structure["blocks"].value
  palette: TAG_List = structure["palette"].value
  oldsize: TAG_List = structure["size"].value
  size: int = oldsize[0].value * oldsize[1].value * oldsize[2].value

  newBlocks = []
  newBlocks2 = []
  newPalette = []

  # new blocks
  startTime = time()
  for i in track(sequence=range(size), description="[green]Allocating Items"):
    newBlocks.append(-1)
    newBlocks2.append(-1)
  print(f"Finished allocating empty blocks in {round((time() - startTime) * 1000, 2)} ms")

  # applying blocks
  startTime = time()
  for block in track(sequence=blocks, description="[green]Applying Blocks"):
    pos = block['pos'].value
    
    index = getStructureBlockIndex(oldsize[1].value, oldsize[2].value, pos[0].value, pos[1].value, pos[2].value)
    newBlocks[index] = block['state'].value
    # newBlocks2[index] = -1 represent air
  print(f"Finished applying blocks in {round((time() - startTime) * 1000, 2)} ms")

  # applying palette
  startTime = time()
  for i in track(sequence=palette, description="[green]Applying Palette"):
    # Using prismarine-data, find the java edition ID
    if not getDynamicBlockIdentifier(i) in blocksj2b:
      newPalette.append(getBlockObject('minecraft:air[]', 'bedrock'))
    else:
      javaId = blocksj2b[getDynamicBlockIdentifier(i)]
      newPalette.append(getBlockObject(javaId, 'bedrock'))
  print(f"Finished applying palette in {round((time() - startTime) * 1000, 2)} ms")

  newStructure = {
    'format_version': TAG_Int(1),
    'size': TAG_List(TAG_Int, oldsize),
    'structure_world_origin': TAG_List(TAG_Int, [0, 0, 0]),
    'structure': TAG_Compound({
      'block_indices': TAG_List(TAG_List, [
        TAG_List(TAG_Int, newBlocks),
        TAG_List(TAG_Int, newBlocks2)
      ]),
      'entities': TAG_List(TAG_Compound, []),
      'palette': TAG_Compound({
        'default': TAG_Compound({
          'block_palette': TAG_List(TAG_Compound, newPalette),
          'block_position_data': TAG_Compound({})
        })
      })
    })
  }
  
  return NBTFile(value=newStructure), size * 8