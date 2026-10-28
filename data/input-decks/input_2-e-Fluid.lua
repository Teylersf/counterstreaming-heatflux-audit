--------------------------------------------------------------------------------
-- App dependencies
--------------------------------------------------------------------------------
-- Load the App and equations to be used
local Moments = require("App.PlasmaOnCartGrid").Moments()
local TenMoment = require "Eq.TenMoment"


--------------------------------------------------------------------------------
-- Preamble
--------------------------------------------------------------------------------
-- Basic constants
local gasGamma = 5./3.  -- gas gamma
local elcCharge = -1.0  -- electron charge
local ionCharge = 1.0   -- ion charge
local elcMass = 1.     -- electron mass 
local lightSpeed = 1.0  -- light speed
local mu0 = 1.0         -- mu_0

-- Problem-specific characteristic parameters
local n0 = 1.                 -- characteristic density variation
local rhofloor = 0.05
local plasmaBetae0 = 0.3        -- thermal pressure vs. magnetic pressure
local plasmaBetai0 = 0.26
local lambda_di0 = 0.5         -- transition layer thickness over ion inertial length
local Ti0_Te0 = 0.8666            -- ion temperature vs. electron temperature
local massRatio = 25.0         -- ion mass vs. electron mass
local vAe0_lightSpeed = 0.5    -- electron Alfven speed vs. c
local perturbationLevel = 0.1  -- relative perturbation magnitude

-- Derived parameters for problem setup or for diagnostic information
local epsilon0 = 1.0 / lightSpeed^2 / mu0          -- epsilon_0
local ionMass = elcMass * massRatio                -- ion mass
local vAe0 = lightSpeed * vAe0_lightSpeed          -- electron Alfven speed
local vAlf0 = vAe0 * math.sqrt(elcMass / ionMass)  -- plasma Alfven speed
local vth_e = 0.111803

local B0 = 0.5
local B0x = 0.05-- math.sqrt((2)*vth_e^2/plasmaBetae0)--vAlf0 * math.sqrt(n0 * ionMass)         -- background B field
local OmegaCi0 = ionCharge * B0 / ionMass          -- ion cyclotron frequency
local OmegaPe0 = math.sqrt(n0 * elcCharge^2 / (epsilon0 * elcMass))
                                                   -- electron plasma frequency
local de0 = lightSpeed / OmegaPe0                  -- electron inertial length
local OmegaPi0 = math.sqrt(n0 * ionCharge^2 / (epsilon0 * ionMass))
                                                   -- ion plasma frequency
local di0 = lightSpeed / OmegaPi0                  -- ion inertial length
local lambda = lambda_di0 * di0                    -- transition layer thickness
local psi0 = perturbationLevel * B0x                -- potential of perturbation B field

-- Domain and time control
local Lx, Ly = 48 * de0, 64 * de0  -- domain lengths
local Nx, Ny = 480, 640                 -- grid size
local tEnd = 600 / OmegaPe0           -- end of simulation
-- local maximumDt = 0.025/OmegaPe0
local nFrame = 60                       -- number of output frames at t=tEnd


--------------------------------------------------------------------------------
-- App construction
--------------------------------------------------------------------------------
local momentApp = Moments.App {
   -----------------------------------------------------------------------------
   -- Common
   -----------------------------------------------------------------------------
   logToFile = true,            -- will log to rt-5m-gem_0.log
   tEnd = tEnd,                 -- stop the simulation at t=tEnd
   nFrame = nFrame,             -- number of output frames at t=tEnd
   lower = {-Lx/2, -Ly/2},      -- lower limit of domain in each direction
   upper = {Lx/2, Ly/2},        -- upper limit of domain in each direction
   cells = {Nx, Ny},            -- number of cells in each direction
   decompCuts = {4,4},
   --useShared = true,
   timeStepper = "fvDimSplit",  -- always use fvDimSplit for fluid simulations,
                                -- i.e., finite-volume dimensional-spli
   --suggestedDt = 0.5*Lx/Nx*(1/math.sqrt(2.)),
   cflFrac=0.666667,
   periodicDirs = {1,2},          -- periodic boundary condition directions

   -----------------------------------------------------------------------------
   -- Species
   -----------------------------------------------------------------------------
   -- electrons
   elc1 = Moments.Species {
      charge = elcCharge, mass = elcMass,  -- charge and mass
      equation = TenMoment { },
                                           -- default equation to be evolved
                                           -- using 2nd-order scheme
      equationInv = TenMoment { numericalFlux = "lax" },
      forceInv=false,
                                           -- backup equation to be solved to
                                           -- retake the time step in case of -- negative density/pressure
      init = function (t, xn)              -- initial condition to set the
                                           -- moments of this species
         local x, y = xn[1], xn[2]

         -- local TeFrac = 1.0 / (1.0 + Ti0_Te0)
         local B1 = B0 * (math.tanh((y+64/4)) - math.tanh((y-64/4)) - 1.0)
         local B2 = psi0 * math.sin(2*math.pi*x/48) + (psi0/4) * math.exp(-((x+12)/6)^(2))
         local B3 = math.sqrt((B0)^2 + (B0x)^2 - (B1)^2)
         local B1y = (1/math.cosh((y+64/4)))^2-(1.0 / math.cosh((y-64/4)))^2
         local T_e = vth_e^2

         local rho_e = n0 * elcMass *(0.03 + (0.94/2)*(math.tanh((y+16)/1)-math.tanh((y-16)/1)))
         local rhovx_e = rho_e * 0.5*B1*B1y/((1)*B3)
         local rhovy_e = 0.0
         local rhovz_e = rho_e * (0.5*B1y/(1) - psi0 * (2*math.pi/48)*math.cos(2*math.pi*x/48)/(1) - (psi0/4) * (-2) * ((x+12)/(6^2)) * math.exp(-((x+12)/6)^(2))/(1))
         
	 local pre_e = rho_e * T_e/elcMass 
	 local pxx_e = pre_e + rhovx_e*rhovx_e/rho_e
	 local pxy_e = rhovx_e*rhovy_e/rho_e
	 local pxz_e = rhovx_e*rhovz_e/rho_e

	 local pyy_e = pre_e + rhovy_e * rhovy_e/rho_e
	 local pyz_e = rhovy_e*rhovz_e/rho_e
	 
	 local pzz_e = pre_e + rhovz_e*rhovz_e/rho_e
	 


         return rho_e, rhovx_e, rhovy_e, rhovz_e, pxx_e, pxy_e, pxz_e, pyy_e, pyz_e, pzz_e
      end,
      evolve = true,                         -- whether to evolve this species
                                             -- in the hyperbolic step; it could
                                             -- still be evolved in the source
                                             -- update step, though
      --bcy = { Euler.bcWall, Euler.bcWall },  -- boundary conditions along
                                             -- non-periodic directions; in this
                                             -- case, the y direction
   },
   elc2 = Moments.Species {
      charge = elcCharge, mass = elcMass,  -- charge and mass
      equation = TenMoment { },
                                           -- default equation to be evolved
                                           -- using 2nd-order scheme
      equationInv = TenMoment { numericalFlux = "lax" },
      forceInv=false,
                                           -- backup equation to be solved to
                                           -- retake the time step in case of -- negative density/pressure
      init = function (t, xn)              -- initial condition to set the
                                           -- moments of this species
         local x, y = xn[1], xn[2]

         -- local TeFrac = 1.0 / (1.0 + Ti0_Te0)
         local B1 = B0 * (math.tanh((y+64/4)) - math.tanh((y-64/4)) - 1.0)
	 local B2 = psi0 * math.sin(2*math.pi*x/48) + (psi0/4) * math.exp(-((x+12)/6)^(2))
	 local B3 = math.sqrt((B0)^2 + (B0x)^2 - (B1)^2)
	 local B1y = (1/math.cosh((y+64/4)))^2-(1.0 / math.cosh((y-64/4)))^2
         local T_e = vth_e^2

         local rho_e = n0 * elcMass * (0.97-(0.94/2)*(math.tanh((y+16)/1)-math.tanh((y-16)/1)))
	 local rhovx_e = rho_e * 0.5*B1*B1y/((1)*B3)
         local rhovy_e = 0.0
         local rhovz_e = rho_e * (0.5*B1y/(1) - psi0 * (2*math.pi/48)*math.cos(2*math.pi*x/48)/(1) - (psi0/4) * (-2) * ((x+12)/(6^2)) * math.exp(-((x+12)/6)^(2))/(1))
         
	 local pre_e = rho_e * T_e/elcMass
	 local pxx_e = pre_e + rhovx_e*rhovx_e/rho_e
	 local pxy_e = rhovx_e*rhovy_e/rho_e
	 local pxz_e = rhovx_e*rhovz_e/rho_e

	 local pyy_e = pre_e + rhovy_e * rhovy_e/rho_e
	 local pyz_e = rhovy_e*rhovz_e/rho_e
	 
	 local pzz_e = pre_e + rhovz_e*rhovz_e/rho_e
	 


         return rho_e, rhovx_e, rhovy_e, rhovz_e, pxx_e, pxy_e, pxz_e, pyy_e, pyz_e, pzz_e
      end,
      evolve = true,                         -- whether to evolve this species
                                             -- in the hyperbolic step; it could
                                             -- still be evolved in the source
                                             -- update step, though
      --bcy = { Euler.bcWall, Euler.bcWall },  -- boundary conditions along
                                             -- non-periodic directions; in this
                                             -- case, the y direction
   },


   -----------------------------------------------------------------------------
   -- Electromagnetic field
   -----------------------------------------------------------------------------
   field = Moments.Field {
      epsilon0 = epsilon0, mu0 = mu0,
      init = function (t, xn)
         local x, y = xn[1], xn[2]
         local pi = math.pi
         local sin = math.sin
         local cos = math.cos

         local Ex, Ey, Ez = 0.0, 0.0, 0.0

         local B1 = B0 * (math.tanh((y+64/4)) - math.tanh((y-64/4)) - 1.0)
	 local B2 = psi0 * math.sin(2*math.pi*x/48) + (psi0/4) * math.exp(-((x+12)/6)^(2))
	 local B3 = math.sqrt((B0)^2 + (B0x)^2 - (B1)^2)
         return Ex, Ey, Ez, B1, B2, B3
      end,
      evolve = true, -- whether to evolve the field in the hyperbolic step; even
                     -- if this is set to false, the E field could still be
                     -- evolved in the source update step
     -- bcy = { Moments.Field.bcReflect, Moments.Field.bcReflect },
                     -- boundary conditions along the nonperiodic directions,
                     -- in this case, the y direction.
   },

   -----------------------------------------------------------------------------
   -- Source equations that couple the plasma fluids and EM fields
   -----------------------------------------------------------------------------
   emSource = Moments.CollisionlessEmSource {
      species = {"elc1","elc2"},  -- plasma species involved
      timeStepper = "direct",    -- time-stepper; one of "time-centered",
                                 -- "direct", and "exact"
   },

   elc1_10mSource = Moments.TenMomentRelaxSource {
	species = {"elc1"},
	timeStepper = "explicit",
	k = 0.1/de0,
   },
   elc2_10mSource = Moments.TenMomentRelaxSource {
	species = {"elc2"},
	timeStepper = "explicit",
	k = 0.1/de0,
   },

}


--------------------------------------------------------------------------------
-- Run the App
--------------------------------------------------------------------------------
momentApp:run()

