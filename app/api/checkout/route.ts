import Stripe from "stripe";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST() {
  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    payment_method_types: ["card"],
    line_items: [
      {
        price: process.env.STRIPE_PRICE_ID!,
        quantity: 1,
      },
    ],
    success_url: `${process.env.NEXT_PUBLIC_SITE_URL}/success`,
    cancel_url: `${process.env.NEXT_PUBLIC_SITE_URL}/cancel`,
  });

  return new Response(
    JSON.stringify({ url: session.url }),
    { status: 200 }
  );
}
