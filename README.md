# My Projects

## Projects developed out of my own curiosity and the passion to one day make this world a better place.

I graduated with an MEng in Chemical Engineering, where I built my coding skills using MATLAB to simulate industrial processes such as fermentation and adsorption using PDE and ODE. 
I have also used Python to simulate chemical interactions using Molecular Dynamics and Monte Carlo methods, and trained machine learning surrogate models (RandomForest, MLP, TensorFlow), which can be found in the **Multiscale Modelling** folder in this repository. 


The **Energy folder** includes the personal projects I developed relating to the energy transition. 

The **UK Power vs European Gas** project was made to test a claim I heard: **is UK power becoming less dependent on gas as solar and wind grow?**

I pulled UK wholesale power prices (2016–2026) from the Elexon API. As the API only allows 7 days per request, I split the range into weekly chunks, fetched them in parallel with retries, and cached the results to CSV. I then merged them with EU gas (TTF), US gas, Brent crude and the EUR/GBP exchange rate from Yahoo Finance.
The key insights include:
- UK power and EU gas are strongly linked over the long term (0.87 correlation on price levels, 0.68 on monthly returns), but only weakly day to day (0.06), as weather dominates short-term prices.
- The regression shows UK power ≈ £30 + 1.66 × gas price (R² = 0.75). The 1.66 matches how much gas a gas power station burns per MWh of electricity, and the £30 is mostly the carbon cost.
- Correlation rises and falls with how much gas prices are moving, so it says more about gas volatility than about how dependent power is on gas.
- A model trained up to July 2026 predicted the August–October rise in power closely (+30% predicted vs +27% actual), so there is no evidence yet that UK power is decoupling from gas.
- Surprisingly, oil and gas prices barely move together (correlation of 0.08).

Next, I plan to add the UK carbon price and wind output to the model, and re-run the test after winter.

The project **Energy Transition** was made with the goal of helping me understand where we are in the energy transition. 
I used an API from WRI to get data on power plants around the world: their installed capacity, location and type. 
This project shows the proportion of installed capacity from renewable plants compared to fossil fuel and nuclear plants, demonstrating which countries have high demand and which countries are more sustainable. 
The key insights include: 
- Currently, the world generates more energy using hydropower than other renewable sources such as wind or solar.
- Only 19.6% of global energy generation comes from renewables.
- 83.4% of Brazil's capacity is renewable, compared to just 21.9% in the USA.
- Less than 50% of UK energy generated in 2017 was from fossil fuel sources.


The **Profit or Planet** project was made to answer a question: **if energy companies generate more money, will they become more sustainable?**

I analysed their financial performance using financial statements extracted from Yahoo Finance. Sustainability performance was analysed using the available ESG scores from Yahoo Finance. 
Both UK and US energy companies were analysed, and all metric units were converted to US units for consistency. 
The companies analysed include ExxonMobil, Shell, BP, Rolls-Royce and Centrica. 

Although the RandomForest machine learning model shows poor correlation between profit margin and ESG score, it shows that the leading energy companies tend to invest more in Social compared to Environmental or Governance. 
Rolls-Royce, as the only nuclear-focused firm, shows a very interesting result that can be seen in the project.



**Note:** Multiscale modelling and the Coanda folders are my past academic projects involving CFD, machine learning surrogate(TensorFlow), multi scale modelling (Monte Carlo and Molecular Dynamics)
