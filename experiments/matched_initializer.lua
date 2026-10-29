-- Aggregate-PIC initializer for the posted legacy Gkeyll Moments API.
-- This module prepares no fields, equations, closures, timesteps or boundaries.
local ffi = require "ffi"

local M = {}

function M.install(options)
   assert(options and options.aggregateFile, "aggregateFile is required")
   local expectedSpecies = assert(options.expectedSpecies)
   assert(expectedSpecies == 1 or expectedSpecies == 2)
   assert(ffi.abi("le") and ffi.sizeof("double") == 8,
          "The exported state requires little-endian float64")

   local file = assert(io.open(options.aggregateFile, "rb"))
   local blob = assert(file:read("*a"))
   file:close()
   local nx, ny, nc = 480, 640, 10
   assert(#blob == nx*ny*nc*8, "Wrong aggregate state length")
   -- Retain the Lua string as well as the pointer for the entire simulation.
   -- A pointer alone does not keep its backing Lua string alive.
   local storage = {blob = blob, ptr = ffi.cast("const double *", blob)}

   local function lookup(xn, weight)
      local ix = math.floor((xn[1]+24)/0.1) % nx
      local iy = math.floor((xn[2]+32)/0.1) % ny
      local offset = (iy*nx+ix)*nc
      local p = storage.ptr
      return weight*p[offset], weight*p[offset+1], weight*p[offset+2],
             weight*p[offset+3], weight*p[offset+4], weight*p[offset+5],
             weight*p[offset+6], weight*p[offset+7], weight*p[offset+8],
             weight*p[offset+9]
   end

   local plasma = require "App.PlasmaOnCartGrid"
   local originalMoments = plasma.Moments
   assert(type(originalMoments) == "function", "Legacy Moments() API required")
   plasma.Moments = function(...)
      -- Only the posted deck's next Moments() call is intercepted.
      plasma.Moments = originalMoments
      local api = originalMoments(...)
      local originalSpecies, originalApp = api.Species, api.App
      local speciesCount = 0
      api.Species = setmetatable({}, {
         __index = originalSpecies,
         __call = function(_, specification)
            speciesCount = speciesCount+1
            assert(speciesCount <= expectedSpecies, "Unexpected extra species")
            assert(specification.mass == 1 and specification.charge == -1,
                   "Unit-mass electron species required")
            local originalInit = assert(specification.init)
            assert(type(originalInit) == "function")
            specification.init = function(t, xn, ...)
               local weight = 1.0
               if expectedSpecies == 2 then
                  -- In the hash-pinned original deck n0=m=1, so its first
                  -- return is exactly its positive smooth fluid label weight.
                  -- No constructor-order or PIC-tag assignment is assumed.
                  weight = originalInit(t, xn, ...)
                  assert(weight >= 0.03-1e-12 and weight <= 0.97+1e-12,
                         "Original fluid label weight outside expected range")
               end
               return lookup(xn, weight)
            end
            return originalSpecies(specification)
         end,
      })
      api.App = setmetatable({}, {
         __index = originalApp,
         __call = function(_, specification)
            assert(speciesCount == expectedSpecies, "Species count mismatch")
            assert(specification.cells[1] == nx and specification.cells[2] == ny)
            assert(specification.lower[1] == -24 and specification.lower[2] == -32)
            assert(specification.upper[1] == 24 and specification.upper[2] == 32)
            assert(specification.decompCuts[1] == 4 and specification.decompCuts[2] == 4)
            assert(specification.periodicDirs[1] == 1 and specification.periodicDirs[2] == 2)
            assert(specification.timeStepper == "fvDimSplit")
            assert(specification.tEnd == 600 and specification.nFrame == 60,
                   "Full control runs must retain original time/output controls")
            return originalApp(specification)
         end,
      })
      return api
   end
end

return M
