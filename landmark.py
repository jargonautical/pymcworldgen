#!/usr/bin/env python

"""

Landmark generation - interspersed landmarks on the terrain

"""

import random
import math
import numpy
from layer import *
from constants import *

class Landmark(Layer):
    """
    A chunk generator for a single landmark somewhere in the world.
    """
    seed = None
    terrainlayer = None
    x = None
    z = None
    y = None
    layermask = None
    
    # Viewrange is a class property only. This is the maximum number of blocks from
    # the centerpoint that this Landmark will generate blocks.
    viewrange = 0
    def __init__(self, seed, terrainlayer, x = 0, z = 0, y = 0, layermask = None):
        """
        Landmark constructor. Random seed necessary. terrainlayer necessary.
        if x and z are None, we generate at a random point? I don't really like that behavior
        how about we generate at 0,0. Layermask can prevent us from spawning in
        certain places, or give us a random probability that we won't spawn in an area.
        """
        self.seed = seed
        self.terrainlayer = terrainlayer
        self.x = x
        self.z = z
        self.y = y
        self.layermask = layermask

    def setpos(self, x, z, y):
        """
        Set the position of this landmark. 
        """
        self.x = x
        self.z = z
        self.y = y

    def setTerrainLayer(self, terrainlayer):
        self.terrainlayer = terrainlayer

    def isLandmarkInChunk(self, cx, cz):
        """
        Determine whether the given chunk contains a portion of this landmark.
        """
        bxrange = (cx*16 - self.viewrange, (cx+1)*CHUNK_WIDTH_IN_BLOCKS + self.viewrange)
        bzrange = (cz*16 - self.viewrange, (cz+1)*CHUNK_WIDTH_IN_BLOCKS + self.viewrange)

        if ( bxrange[0] <= self.x < bxrange[1] ) and ( bzrange[0] <= self.z < bzrange[1] ):
            return True
        else:
            return False

    def editChunk(self, cornerblockx, cornerblockz, terrainchunk):
        # Dummy: output a wood block at height 105.
        # where in the array does this block belong?
        relx = self.x - cornerblockx
        relz = self.z - cornerblockz
        # only place this down if we're not going to overflow the array
        if ( 0 <= relx < CHUNK_WIDTH_IN_BLOCKS ) and ( 0 <= relz < CHUNK_WIDTH_IN_BLOCKS ):
            terrainchunk[relx, relz, 0:CHUNK_HEIGHT_IN_BLOCKS] = MAT_WOOD
            terrainchunk[relx, relz, self.y] = MAT_WATER
        
    def getChunk(self, cx, cz):
        """
        Output a chunk for processing. 
        """
        # If we aren't in this chunk, either act as a passthru or return an opaque chunk.
        if not self.isLandmarkInChunk(cx, cz):
            return self.terrainlayer.getChunk(cx, cz)
        # If we are in the chunk, let's write our blocks to the output chunk
        terrainchunk = self.terrainlayer.getChunk(cx, cz)
        outputchunk = terrainchunk
        self.editChunk(cx*CHUNK_WIDTH_IN_BLOCKS, cz*CHUNK_WIDTH_IN_BLOCKS, terrainchunk)
        return outputchunk

class LandmarkGenerator(Layer):
    """
    A chunk generator for a random smattering of landmarks throughout the worldde
    """
    seed = None
    terrainlayer = None
    landmarklist = None
    density = None

    # { dict where key is (rx, rz) and value is {dict where key is (cx, cz) and value is [list of Landmarks ] } }
    worldspawns = None 

    def __init__(self, seed, terrainlayer, landmarklist = [Landmark], density = 200):
        self.seed = seed        
        self.terrainlayer = terrainlayer
        self.density = density
        # Input landmark list needs to be doublechecked.
        for lmtype in landmarklist:
            if not issubclass(lmtype, Landmark): raise TypeError, "landmarklist must only contain Landmark types."
        self.landmarklist = landmarklist
        # This data structure has a lot of indexing structure so we can find relevant points quickly
        self.worldspawns = {} 

    def getMaxViewRange(self):
        mvr = 0
        for lmtype in self.landmarklist:
            if lmtype.viewrange > mvr: mvr = lmtype.viewrange
        return mvr

    def getSpawnsInRegion(self, rx, rz):
        # Generate each spawn point and store in regionspawns, otherwise we just get the cached spawnpoints.
        if not (rx, rz) in self.worldspawns:
            # Seed the random number gen with all 64 bits of region coordinate data by using both seed and jumpahead
            random.seed( self.seed ^ ((rx & 0xFFFF0000) | (rz & 0x0000FFFF)) )
            random.jumpahead( ((rx & 0xFFFF0000) | (rz & 0x0000FFFF)) ) 
            # First number should be number of points in region
            numspawns = self.density

            self.worldspawns[ (rx,rz) ] = {}
            currentregion = self.worldspawns[ (rx,rz) ]
            for ix in xrange(numspawns):
                blockx = random.randint( 0, CHUNK_WIDTH_IN_BLOCKS * REGION_WIDTH_IN_CHUNKS - 1 ) + rx * CHUNK_WIDTH_IN_BLOCKS * REGION_WIDTH_IN_CHUNKS
                blockz = random.randint( 0, CHUNK_WIDTH_IN_BLOCKS * REGION_WIDTH_IN_CHUNKS - 1 ) + rz * CHUNK_WIDTH_IN_BLOCKS * REGION_WIDTH_IN_CHUNKS
                blocky = random.randint( 0, CHUNK_HEIGHT_IN_BLOCKS - 1 ) 
                currchunkx = blockx / CHUNK_WIDTH_IN_BLOCKS
                currchunkz = blockz / CHUNK_WIDTH_IN_BLOCKS
                # We store the points for each chunk indexed by chunk
                if not (currchunkx, currchunkz) in currentregion:
                    currentregion[ (currchunkx, currchunkz) ] = []
                # We make a landmark for each point
                lmtypeix = random.randint(0, len(self.landmarklist) - 1)
                lmtype = self.landmarklist[lmtypeix] 
                lm = lmtype(self.seed, self.terrainlayer, blockx, blockz, blocky)
                # Lastly we append the landmark to the chunk
                currentregion[ (currchunkx, currchunkz) ].append( lm )
        return self.worldspawns[ (rx,rz) ]
        

    def getSpawnsInChunk(self, cx, cz):
        """
        Gets the spawn points for the selected chunk (reading from the appropriate region cache) 
        """
        rx = cx / REGION_WIDTH_IN_CHUNKS
        rz = cz / REGION_WIDTH_IN_CHUNKS
        regionspawns = self.getSpawnsInRegion(rx, rz)
        if (cx, cz) in regionspawns:
            return regionspawns[ (cx,cz) ]
        else:
            return None
        

    def getSpawnsTouchingChunk(self, cx, cz):
        """
        Gets the spawns within the maximum view range for this landmark generator, rounded up
        to the nearest chunk multiple (for speed of moving the data around.) The landmark generator
        can check on its own whether it's within rendering range of the chunk.
        """
        mvr = self.getMaxViewRange()
        chunkviewrange = (mvr + CHUNK_WIDTH_IN_BLOCKS - 1) / CHUNK_WIDTH_IN_BLOCKS # ceiling div
        spawnlist = []
        for chunkrow in xrange( cx - chunkviewrange, cx + chunkviewrange + 1):
            for chunkcol in xrange( cz - chunkviewrange, cz + chunkviewrange + 1):
                chunkspawns = self.getSpawnsInChunk( chunkrow, chunkcol )
                if chunkspawns != None: spawnlist.extend( chunkspawns )
        return spawnlist

    def getChunk(self, cx, cz):
        """
        Add the landmarks to the existing terrain
        """
        # We build a graph of landmarks, then get a chunk from the entire graph.
        graph = self.terrainlayer
        landmarks = self.getSpawnsTouchingChunk(cx,cz)
        if landmarks == None:
            return self.terrainlayer.getChunk( cx, cz )
        for mark in landmarks:
            # insert this landmark at the end of the graph    
            mark.setTerrainLayer( graph )
            graph = mark

        return graph.getChunk( cx, cz )
        
